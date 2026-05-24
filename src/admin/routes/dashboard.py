"""Dashboard route — заглушка. Реальные счётчики — после TASK-024+."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..app import templates

__all__ = ["router"]


router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Главная админки — заглушка. Auth подключится в TASK-020."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "counters": {
                "users": 0,
                "events": 0,
                "categories": 0,
                "predictions": 0,
            },
        },
    )
