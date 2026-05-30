"""Login routes — GET форма, POST verify, /logout (TASK-020)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import get_settings
from src.shared.db import SessionLocal
from src.shared.exceptions import AdminInactiveError, AdminInvalidCredentialsError
from src.shared.logging import get_logger
from src.shared.services import AdminAuthService

from ..app import templates
from ..auth.security import (
    CSRF_COOKIE_NAME,
    CSRF_COOKIE_NAME_PROD,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_NAME_PROD,
    create_session_token,
)

__all__ = ["router"]

logger = get_logger(__name__)

router = APIRouter(tags=["auth"])


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def _login_rate_limit(request: Request) -> None:
    """Rate limit for /login endpoint: 5 attempts per minute per IP+login.

    Extracts login from form data to create a combined key.
    This prevents credential stuffing while allowing legitimate users
    to try different accounts.
    """
    from fastapi_limiter import FastAPILimiter

    # Skip rate limiting if FastAPILimiter.redis is not set (tests)
    if not FastAPILimiter.redis:
        return

    client_host = request.client.host if request.client else ""
    try:
        form = await request.form()
        login = form.get("login", "")
    except Exception:
        login = ""

    key = f"{client_host}:{login}"

    # Check rate limit: 5 requests per 60 seconds
    redis = FastAPILimiter.redis
    rate_key = f"fastapi-limiter:login:{key}"
    current = await redis.incr(rate_key)
    if current == 1:
        await redis.expire(rate_key, 60)

    if current > 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


def _render_login_error(
    request: Request,
    csrf_protect: CsrfProtect,
    *,
    error: str,
    status_code: int,
) -> Response:
    """Re-render формы логина с ошибкой; использует существующую CSRF-куку если есть.

    TASK-068: если валидная CSRF-кука уже есть — извлекаем токен из неё и
    НЕ перезаписываем куку. Это предотвращает рассинхрон при повторном сабмите.
    """
    from itsdangerous import BadData, URLSafeTimedSerializer

    s = get_settings()
    csrf_name = CSRF_COOKIE_NAME_PROD if s.environment != "dev" else CSRF_COOKIE_NAME
    existing_cookie = request.cookies.get(csrf_name)

    csrf_token: str
    signed_token: str

    if existing_cookie:
        # Пробуем извлечь токен из существующей куки
        try:
            serializer = URLSafeTimedSerializer(
                s.admin.csrf_secret.get_secret_value(), salt="fastapi-csrf-token"
            )
            token: str | None = serializer.loads(existing_cookie, max_age=None)
            if token:
                csrf_token = token
                signed_token = existing_cookie
                # Используем существующую куку — не ставим новую
                request.state.csrf_token = csrf_token
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={"error": error},
                    status_code=status_code,
                )
        except (BadData, Exception):
            # Кука невалидна — упадём до генерации новой
            pass

    # Куки нет или невалидна — генерируем новую пару
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    request.state.csrf_token = csrf_token
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error},
        status_code=status_code,
    )
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    # CSRF token + cookie ставит CsrfTokenMiddleware (TASK-022).
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
    _rate_limit: None = Depends(_login_rate_limit),
) -> Response:
    # CsrfProtectError ловится global exception handler в app.py.
    await csrf_protect.validate_csrf(request)

    service = AdminAuthService(session)
    try:
        admin = await service.authenticate(login=login, password=password)
    except AdminInvalidCredentialsError:
        logger.info(
            "admin.auth.failed",
            login=login,
            ip=request.client.host if request.client else None,
        )
        return _render_login_error(
            request,
            csrf_protect,
            error="Неверный логин или пароль.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    except AdminInactiveError:
        logger.warning("admin.auth.inactive", login=login)
        return _render_login_error(
            request,
            csrf_protect,
            error="Учётная запись отключена. Обратитесь к администратору.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    token = create_session_token(admin_id=admin.id)
    s = get_settings()
    expires = datetime.now(tz=UTC) + timedelta(hours=s.admin.session_hours)

    session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
    redirect = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=session_name,
        value=token,
        httponly=True,
        secure=s.environment != "dev",
        samesite=s.admin.session_samesite,
        expires=expires,
        path="/",  # __Host- cookies ТРЕБУЮТ явный Path=/
    )

    # Ротация CSRF-куки при успешном логине (fresh token)
    _, signed_csrf = csrf_protect.generate_csrf_tokens()
    csrf_protect.set_csrf_cookie(signed_csrf, redirect)

    logger.info("admin.auth.success", admin_id=admin.id, login=admin.login)
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    s = get_settings()
    session_name = SESSION_COOKIE_NAME_PROD if s.environment != "dev" else SESSION_COOKIE_NAME
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(session_name, path="/")  # __Host- cookies ТРЕБУЕТ path=/
    logger.info("admin.auth.logout")
    return response
