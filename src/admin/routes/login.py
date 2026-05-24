"""Login route — форма входа. Реальная обработка POST — TASK-020."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..app import templates

__all__ = ["router"]


router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    """Форма входа — отрендерена, POST пока не обрабатывается (405)."""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )
