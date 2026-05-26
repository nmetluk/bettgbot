"""Общие helper'ы для admin routes."""

from __future__ import annotations

from fastapi import Request, Response
from fastapi_csrf_protect import CsrfProtect

__all__ = ["set_fresh_csrf_token"]


def set_fresh_csrf_token(
    request: Request,
    response: Response,
    csrf_protect: CsrfProtect,
) -> Response:
    """Генерирует свежий CSRF токен, записывает в request.state и ставит cookie.

    Унифицирует паттерн из _render_login_error и _render_form для всех handler'ов,
    которые возвращают HTML/HTMX-fragment с формой после write-операции.

    Args:
        request: FastAPI request — записывает csrf_token в request.state
        response: FastAPI response — в response добавляется Set-Cookie header
        csrf_protect: CsrfProtect dependency — генерирует токены

    Returns:
        Тот же response с добавленным Set-Cookie заголовком.
    """
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    request.state.csrf_token = csrf_token
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response
