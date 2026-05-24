"""Dashboard route — заглушка. Реальные счётчики — после TASK-024+."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.shared.models import AdminUser

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]


router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin: AdminUser = Depends(current_admin),
) -> HTMLResponse:
    """Главная админки — защищена middleware + dependency."""
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
            "admin": admin,
        },
    )
