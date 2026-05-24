"""RequireAdminMiddleware — защищает все пути, кроме whitelisted (TASK-020).

ASGI-callable (не `BaseHTTPMiddleware`), чтобы избежать двойной буферизации
тел запросов и поддержать streaming. Проверяет signed cookie, подгружает
`AdminUser`, кладёт в `scope.state.admin`, рефрешит cookie на каждом запросе
(sliding TTL).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.config import get_settings
from src.shared.db import SessionLocal
from src.shared.logging import get_logger
from src.shared.models import AdminUser

from .security import SESSION_COOKIE_NAME, create_session_token, verify_session_token

__all__ = ["RequireAdminMiddleware"]

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
        cookie_header = (
            f"{SESSION_COOKIE_NAME}={new_token}; "
            f"HttpOnly; Secure; SameSite=Lax; Path=/; "
            f"Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}"
        )

        async def send_with_cookie(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", cookie_header.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)
