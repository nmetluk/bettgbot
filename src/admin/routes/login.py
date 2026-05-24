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
from ..auth.security import SESSION_COOKIE_NAME, create_session_token

__all__ = ["router"]

logger = get_logger(__name__)

router = APIRouter(tags=["auth"])


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "csrf_token": csrf_token},
    )
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.post(
    "/login",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
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
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Неверный логин или пароль.",
                "csrf_token": csrf_token,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        csrf_protect.set_csrf_cookie(signed_token, response)
        return response
    except AdminInactiveError:
        logger.warning("admin.auth.inactive", login=login)
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
        response = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Учётная запись отключена. Обратитесь к администратору.",
                "csrf_token": csrf_token,
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )
        csrf_protect.set_csrf_cookie(signed_token, response)
        return response

    token = create_session_token(admin_id=admin.id)
    s = get_settings()
    expires = datetime.now(tz=UTC) + timedelta(hours=s.admin.session_hours)

    redirect = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        expires=expires,
        path="/",
    )
    logger.info("admin.auth.success", admin_id=admin.id, login=admin.login)
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    logger.info("admin.auth.logout")
    return response
