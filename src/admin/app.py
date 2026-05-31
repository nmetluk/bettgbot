"""FastAPI admin app (TASK-019/TASK-020).

Каркас: статика, Jinja2-шаблоны, healthcheck, signed-cookie auth-middleware,
rate-limit на /login через Redis, CSRF на POST.

Запуск: `make admin` (или `uv run uvicorn src.admin.app:app --reload`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from hashlib import md5
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi_csrf_protect.load_config import LoadConfig
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.shared.build_info import get_build_info
from src.shared.config import get_settings
from src.shared.logging import configure_logging, get_logger
from src.shared.observability import init_sentry
from src.shared.time import utcnow

from ._security_headers import SecurityHeadersMiddleware
from .auth.middleware import CsrfTokenMiddleware, RequireAdminMiddleware
from .auth.security import CSRF_COOKIE_NAME, CSRF_COOKIE_NAME_PROD, CSRF_TTL_SECONDS

__all__ = ["app", "templates"]


logger = get_logger(__name__)

_BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
# `now()` доступен в шаблонах для расчёта статус-бэйджей событий.
templates.env.globals["now"] = utcnow


# Кастомный фильтр для форматирования даты
def _strftime_filter(dt: datetime, fmt: str = "%d.%m %H:%M") -> str:
    if dt is None:
        return ""
    return dt.strftime(fmt)


templates.env.filters["strftime"] = _strftime_filter


def _static_version(path: str) -> str:
    """Compute short content hash for cache-busting of own admin static assets.
    Called once at startup. Only for our editable files (ui.js, app.css, tokens.css).
    """
    full_path = _BASE_DIR / "static" / path
    if not full_path.exists():
        return "dev"
    data = full_path.read_bytes()
    # MD5 is safe here: used only for cache-busting / content fingerprinting, not cryptography.
    return md5(data, usedforsecurity=False).hexdigest()[:8]


STATIC_VERSIONS: dict[str, str] = {
    "css/tokens.css": _static_version("css/tokens.css"),
    "css/app.css": _static_version("css/app.css"),
    "js/ui.js": _static_version("js/ui.js"),
}


def static_url(path: str) -> str:
    """Jinja helper for versioned static URLs (TASK-094 cache-busting).
    Usage in templates: {{ static_url('css/app.css') }}
    """
    v = STATIC_VERSIONS.get(path, "dev")
    return f"/static/{path}?v={v}"


templates.env.globals["static_url"] = static_url


class StaticCacheControlMiddleware(BaseHTTPMiddleware):
    """TASK-094: proper Cache-Control for /static.

    - Assets with ?v= (our busting) or versioned vendor filenames → immutable long cache.
    - Others → short cache with revalidate.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[StarletteResponse]]
    ) -> StarletteResponse:
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            query = str(request.url.query)
            path = request.url.path
            if "v=" in query or any(x in path for x in ("bootstrap", "htmx", "alpine")):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
        return response


@CsrfProtect.load_config  # type: ignore[arg-type]
def _csrf_config() -> LoadConfig:
    s = get_settings()
    return LoadConfig(
        secret_key=s.admin.csrf_secret.get_secret_value(),
        # Имя куки должно совпадать с тем, что ставит CsrfTokenMiddleware.
        cookie_key=CSRF_COOKIE_NAME_PROD if s.environment != "dev" else CSRF_COOKIE_NAME,
        # Форма постит csrf_token полем тела, не header'ом.
        token_location="body",
        token_key="csrf_token",
        # TASK-068/TASK-069: явный TTL CSRF-токена — 15 минут.
        # CSRF_TTL_SECONDS константа синхронизирована с middleware.
        max_age=CSRF_TTL_SECONDS,
        cookie_secure=s.environment != "dev",
        cookie_samesite="lax",
        # CSRF только на изменяющие методы.
        methods={"POST", "PUT", "PATCH", "DELETE"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()

    # Инициализируем Sentry (если SENTRY_DSN задан)
    init_sentry(
        dsn=s.observability.sentry_dsn,
        environment=s.environment,
        service="admin",
        traces_sample_rate=s.observability.sentry_traces_sample_rate,
    )

    redis_client: Redis = Redis.from_url(str(s.redis_url), decode_responses=True)
    await FastAPILimiter.init(redis_client)
    logger.info("admin.startup", redis=str(s.redis_url))
    try:
        yield
    finally:
        await FastAPILimiter.close()
        await redis_client.aclose()
        logger.info("admin.shutdown")


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level, s.log_format)

    info = get_build_info()
    app = FastAPI(
        title="Betting Bot Admin",
        version=info.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    # Static до middleware: /static/* идёт без auth-проверки.
    app.mount(
        "/static",
        StaticFiles(directory=str(_BASE_DIR / "static")),
        name="static",
    )

    # Порядок middleware (Starlette/FastAPI правило):
    # Последний вызов add_middleware становится outermost (выполняется первым на входящем запросе).
    # Здесь outermost = SecurityHeadersMiddleware (добавлен последним).
    # Далее (в порядке выполнения на request): RequireAdmin → CsrfToken → ProxyHeaders (innermost).
    # ProxyHeaders применяет X-Forwarded-* (полезно, если за nginx/uvicorn с --proxy-headers).
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    app.add_middleware(CsrfTokenMiddleware)
    app.add_middleware(RequireAdminMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(StaticCacheControlMiddleware)  # TASK-094: after others for /static responses

    @app.exception_handler(CsrfProtectError)
    async def _csrf_error_handler(request: Request, exc: CsrfProtectError) -> Any:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Сессия истекла, обновите страницу.",
                "csrf_token": "",
            },
            status_code=403,
        )

    # Импорты локально — routes используют `templates` отсюда (circular avoidance).
    from .routes import analytics as analytics_routes
    from .routes import audit as audit_routes
    from .routes import broadcasts as broadcasts_routes
    from .routes import categories as categories_routes
    from .routes import dashboard as dashboard_routes
    from .routes import events as events_routes
    from .routes import leaderboard as leaderboard_routes
    from .routes import login as login_routes
    from .routes import outcomes as outcomes_routes
    from .routes import users as users_routes

    app.include_router(login_routes.router)
    app.include_router(dashboard_routes.router)
    app.include_router(categories_routes.router)
    app.include_router(events_routes.router)
    app.include_router(outcomes_routes.router)
    app.include_router(users_routes.router)
    app.include_router(leaderboard_routes.router)
    app.include_router(analytics_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(broadcasts_routes.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> Response:
        """Health check with build metadata exposed via HTTP headers.

        Extremely useful for load balancers, monitoring systems,
        and incident investigation ("which exact commit is running?").
        """
        info = get_build_info()
        return JSONResponse(
            {"status": "ok"},
            headers={
                "X-Build-Version": info.app_version,
                "X-Build-Commit": info.git_commit_short,
                "X-Build-Branch": info.git_branch,
                "X-Build-Time": info.build_time,
                "X-Build-Tag": info.git_tag or "",
            },
        )

    return app


app = create_app()
