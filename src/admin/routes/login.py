"""Login routes — GET форма, POST verify, /logout (TASK-020)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi_csrf_protect import CsrfProtect
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import get_settings
from src.shared.db import SessionLocal
from src.shared.exceptions import AdminInactiveError, AdminInvalidCredentialsError
from src.shared.logging import get_logger
from src.shared.services import AdminAuthService

from ..app import templates
from ..auth.security import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_NAME_PROD,
    create_session_token,
)

__all__ = ["router"]

logger = get_logger(__name__)

router = APIRouter(tags=["auth"])


async def _login_rate_limit_identifier(request: Request) -> str:
    """Extract login from form for rate limiting.

    Rate limit is per-IP + per-login to prevent credential stuffing
    while allowing legitimate users to try different accounts.
    """
    client_host = request.client.host if request.client else ""
    # Parse form data to get login field
    try:
        form = await request.form()
        login = form.get("login", "")
    except Exception:
        login = ""
    return f"{client_host}:{login}"


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _render_login_error(
    request: Request,
    csrf_protect: CsrfProtect,
    *,
    error: str,
    status_code: int,
) -> Response:
    """Re-render формы логина с ошибкой; генерирует CSRF (middleware POST не покрывает)."""
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
    _rate_limit: None = Depends(
        RateLimiter(
            times=5,
            seconds=60,
            identifier=_login_rate_limit_identifier,
        )
    ),
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
    if s.environment == "dev":
        redirect.set_cookie(
            key=session_name,
            value=token,
            httponly=True,
            secure=False,
            samesite=s.admin.session_samesite,
            expires=expires,
            path="/",
        )
    else:
        # __Host- cookies: browser подставляет Path=/, Secure
        redirect.set_cookie(
            key=session_name,
            value=token,
            httponly=True,
            secure=True,
            samesite=s.admin.session_samesite,
            expires=expires,
        )

    # Fresh CSRF cookie при успешном login
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
    # __Host- cookies не требуют path (browser подставляет /=/)
    if s.environment == "dev":
        response.delete_cookie(session_name, path="/")
    else:
        response.delete_cookie(session_name)
    logger.info("admin.auth.logout")
    return response
