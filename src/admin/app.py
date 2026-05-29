"""FastAPI admin app (TASK-019/TASK-020).

Каркас: статика, Jinja2-шаблоны, healthcheck, signed-cookie auth-middleware,
rate-limit на /login через Redis, CSRF на POST.

Запуск: `make admin` (или `uv run uvicorn src.admin.app:app --reload`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from fastapi_csrf_protect.load_config import LoadConfig
from fastapi_limiter import FastAPILimiter
from redis.asyncio import Redis

from src.shared.config import get_settings
from src.shared.logging import configure_logging, get_logger
from src.shared.observability import init_sentry

from ._security_headers import SecurityHeadersMiddleware
from .auth.middleware import CsrfTokenMiddleware, RequireAdminMiddleware

__all__ = ["app", "templates"]


logger = get_logger(__name__)

_BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
# `now()` доступен в шаблонах для расчёта статус-бэйджей событий.
templates.env.globals["now"] = lambda: datetime.now(tz=UTC)


@CsrfProtect.load_config  # type: ignore[arg-type]
def _csrf_config() -> LoadConfig:
    s = get_settings()
    return LoadConfig(
        secret_key=s.admin.csrf_secret.get_secret_value(),
        # Форма постит csrf_token полем тела, не header'ом.
        token_location="body",
        token_key="csrf_token",
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

    app = FastAPI(
        title="Betting Bot Admin",
        version="0.0.0",
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

    # Порядок: add_middleware добавляет в обратном порядке выполнения.
    # CsrfTokenMiddleware добавляем ПЕРВЫМ → он inner (после Require).
    # RequireAdminMiddleware ВТОРЫМ → он outer, обрабатывает запрос первым.
    # SecurityHeadersMiddleware ТРЕТЬИМ → outermost, добавляет headers ко всем response.
    app.add_middleware(CsrfTokenMiddleware)
    app.add_middleware(RequireAdminMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

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

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
