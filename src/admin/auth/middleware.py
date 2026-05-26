"""Auth middlewares админки (TASK-020 + TASK-022).

`RequireAdminMiddleware`: защищает все пути, кроме whitelisted. ASGI-callable,
sliding TTL.

`CsrfTokenMiddleware`: для GET-под-auth генерирует `csrf_token` в `request.state`
+ ставит `fastapi-csrf-token` cookie. Шаблоны читают `{{ request.state.csrf_token }}`
без необходимости генерировать в каждом handler'е.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.config import get_settings
from src.shared.db import SessionLocal
from src.shared.logging import get_logger
from src.shared.models import AdminUser

from .security import (
    CSRF_COOKIE_NAME,
    CSRF_COOKIE_NAME_PROD,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_NAME_PROD,
    create_session_token,
    verify_session_token,
)

__all__ = ["CsrfTokenMiddleware", "RequireAdminMiddleware"]

logger = get_logger(__name__)

_PUBLIC_PATHS = frozenset({"/login", "/logout", "/healthz"})
_PUBLIC_PREFIXES = ("/static/",)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


class RequireAdminMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.app = app
        # `session_maker` можно инжектнуть в тестах; production резолвит
        # лениво через `_get_session_maker`, чтобы `patch(... .SessionLocal, ...)`
        # внутри теста влиял на инстанс, созданный в lifespan приложения.
        self._session_maker = session_maker

    def _get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        if self._session_maker is not None:
            return self._session_maker
        # Импорт-время `SessionLocal` мы патчим в тестах через
        # `patch("src.admin.auth.middleware.SessionLocal", ...)`.
        return SessionLocal

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        path = request.url.path

        if _is_public(path):
            await self.app(scope, receive, send)
            return

        token = request.cookies.get(SESSION_COOKIE_NAME)
        admin_id = verify_session_token(token) if token else None
        if admin_id is None:
            await RedirectResponse(url="/login", status_code=302)(scope, receive, send)
            return

        async with self._get_session_maker()() as session:
            admin = await session.get(AdminUser, admin_id)

        if admin is None or not admin.is_active:
            # Cookie валидна, но admin удалён / деактивирован после issue.
            logger.warning("admin.auth.stale_session", admin_id=admin_id)
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(SESSION_COOKIE_NAME, path="/")
            await response(scope, receive, send)
            return

        # AdminUser в request.state для current_admin dependency.
        state: dict[str, Any] = scope.setdefault("state", {})
        state["admin"] = admin

        # Sliding TTL: переоформляем cookie на каждом запросе.
        new_token = create_session_token(admin_id=admin.id)
        s = get_settings()
        expires = datetime.now(tz=UTC) + timedelta(hours=s.admin.session_hours)

        # В prod используем __Host- prefix (browser enforce'ит Secure, Path=/)
        session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
        cookie_parts = [
            f"{session_name}={new_token}",
            "HttpOnly",
            f"SameSite={s.admin.session_samesite.capitalize()}",
            f"Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}",
        ]
        if s.environment == "dev":
            cookie_parts.append("Path=/")
        # __Host- cookies не требуют Path (browser подставляет /=/)

        if s.environment != "dev":
            cookie_parts.append("Secure")
        cookie_header = "; ".join(cookie_parts)

        async def send_with_cookie(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_header.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)


class CsrfTokenMiddleware:
    """Для GET под auth кладёт `csrf_token` в `request.state` + cookie.

    Шаблоны читают `{{ request.state.csrf_token }}`, handler'у не нужно
    генерировать токен вручную. POST/PUT/PATCH/DELETE по-прежнему verify'ятся
    через `csrf_protect.validate_csrf(request)` в handler'ах.

    Порядок: `RequireAdminMiddleware` должен отработать ДО этого middleware,
    чтобы `scope["state"]["admin"]` был выставлен. В `app.add_middleware`
    добавляй CsrfTokenMiddleware ПЕРВЫМ (он inner), RequireAdminMiddleware
    ВТОРЫМ (он outer, обрабатывает запрос первым).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        state = scope.setdefault("state", {})

        # Генерируем токен для всех GET (включая /login, /healthz), кроме статики:
        # — POST не нуждается (форма прислала токен).
        # — статика — лишний оверхед.
        path = request.url.path
        if request.method != "GET" or path.startswith("/static/") or path == "/healthz":
            await self.app(scope, receive, send)
            return

        csrf_protect = CsrfProtect()
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
        state["csrf_token"] = csrf_token

        s = get_settings()
        csrf_name = CSRF_COOKIE_NAME_PROD if s.environment != "dev" else CSRF_COOKIE_NAME
        cookie_parts = [
            f"{csrf_name}={signed_token}",
            "HttpOnly",
            f"SameSite={s.admin.session_samesite.capitalize()}",
        ]
        if s.environment == "dev":
            cookie_parts.append("Path=/")
        # __Host- cookies не требуют Path

        if s.environment != "dev":
            cookie_parts.append("Secure")
        cookie_header = "; ".join(cookie_parts)

        async def send_with_csrf_cookie(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_header.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_csrf_cookie)
