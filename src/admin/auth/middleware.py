"""Auth middlewares админки (TASK-020 + TASK-022 + TASK-068).

`RequireAdminMiddleware`: защищает все пути, кроме whitelisted. ASGI-callable,
sliding TTL.

`CsrfTokenMiddleware`: для GET-под-auth генерирует `csrf_token` в `request.state`
+ ставит `fastapi-csrf-token` cookie. Шаблоны читают `{{ request.state.csrf_token }}`
без необходимости генерировать в каждом handler'е.

TASK-068: НЕ ротирует существующую валидную CSRF-куку на каждый GET — извлекает
токен из уже стоящей куки, чтобы пара (форма-токен ↔ кука) не разрушалась
фоновыми запросами (favicon, второй GET, HTMX).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi_csrf_protect import CsrfProtect
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.shared.config import get_settings
from src.shared.db import SessionLocal
from src.shared.logging import get_logger
from src.shared.models import AdminUser
from src.shared.time import utcnow

from .security import (
    CSRF_COOKIE_NAME,
    CSRF_COOKIE_NAME_PROD,
    CSRF_TTL_SECONDS,
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

        s = get_settings()
        session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
        token = request.cookies.get(session_name)
        admin_id = verify_session_token(token) if token else None
        if admin_id is None:
            await RedirectResponse(url="/login", status_code=302)(scope, receive, send)
            return

        async with self._get_session_maker()() as session:
            admin = await session.get(AdminUser, admin_id)

        if admin is None or not admin.is_active:
            # Cookie валидна, но admin удалён / деактивирован после issue.
            logger.warning("admin.auth.stale_session", admin_id=admin_id)
            s = get_settings()
            session_name = (
                SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
            )
            response = RedirectResponse(url="/login", status_code=302)
            response.delete_cookie(session_name, path="/")
            await response(scope, receive, send)
            return

        # AdminUser в request.state для current_admin dependency.
        state: dict[str, Any] = scope.setdefault("state", {})
        state["admin"] = admin

        # Sliding TTL: переоформляем cookie на каждом запросе.
        new_token = create_session_token(admin_id=admin.id)
        s = get_settings()
        expires = utcnow() + timedelta(hours=s.admin.session_hours)

        # В prod используем __Host- prefix (browser enforce'ит Secure, Path=/)
        session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
        cookie_parts = [
            f"{session_name}={new_token}",
            "HttpOnly",
            f"SameSite={s.admin.session_samesite.capitalize()}",
            f"Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}",
            "Path=/",  # __Host- cookies ТРЕБУЮТ явный Path=/
        ]

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

    TASK-068: если валидная CSRF-кука уже есть — НЕ перезаписывает её, а
    извлекает unsigned-токен из подписанной куки для формы. Это предотвращает
    рассинхрон (форма-токен ↔ кука) при фоновых GET-запросах (favicon, второй GET).

    Порядок: `RequireAdminMiddleware` должен отработать ДО этого middleware,
    чтобы `scope["state"]["admin"]` был выставлен. В `app.add_middleware`
    добавляй CsrfTokenMiddleware ПЕРВЫМ (он inner), RequireAdminMiddleware
    ВТОРЫМ (он outer, обрабатывает запрос первым).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def _get_token_from_cookie(self, signed_token: str, secret_key: str) -> str | None:
        """Декодирует подписанную CSRF-куку и возвращает unsigned токен.

        Если кука невалидна/истекла — возвращает None. Использует тот же
        serializer и max_age, что и CsrfProtect.validate_csrf (TASK-069).
        """
        try:
            serializer = URLSafeTimedSerializer(secret_key, salt="fastapi-csrf-token")
            # TASK-069: декодируем с тем же TTL, что и validate_csrf.
            # Просроченная кука → SignatureExpired → None → будет выдана свежая.
            token: str | None = serializer.loads(signed_token, max_age=CSRF_TTL_SECONDS)
            return token
        except (BadData, Exception):
            # Кука невалидна, истекла или повреждена — сгенерируем новую
            return None

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

        s = get_settings()
        csrf_name = CSRF_COOKIE_NAME_PROD if s.environment != "dev" else CSRF_COOKIE_NAME
        existing_cookie = request.cookies.get(csrf_name)

        csrf_token: str
        signed_token: str
        set_new_cookie = False

        if existing_cookie:
            # TASK-068: пробуем извлечь токен из существующей куки
            secret_key = s.admin.csrf_secret.get_secret_value()
            extracted = self._get_token_from_cookie(existing_cookie, secret_key)
            if extracted:
                # Кука валидна — используем её токен, НЕ перезаписываем
                csrf_token = extracted
                signed_token = existing_cookie
                # set_new_cookie остаётся False
            else:
                # Кука невалидна/истекла — генерируем новую пару
                csrf_protect = CsrfProtect()
                csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
                set_new_cookie = True
        else:
            # Куки нет — генерируем новую пару
            csrf_protect = CsrfProtect()
            csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
            set_new_cookie = True

        state["csrf_token"] = csrf_token

        if not set_new_cookie:
            # Кука уже есть и валидна — не перезаписываем
            await self.app(scope, receive, send)
            return

        cookie_parts = [
            f"{csrf_name}={signed_token}",
            "HttpOnly",
            f"SameSite={s.admin.session_samesite.capitalize()}",
            "Path=/",  # __Host- cookies ТРЕБУЮТ явный Path=/
        ]

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
