"""Dashboard route — главная страница админки со счётчиками."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.models import AdminUser
from src.shared.services import DashboardService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]


router = APIRouter(tags=["dashboard"])


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """Главная админки — счётчики, активные события, последние действия."""
    service = DashboardService(session)
    counters = await service.get_counters()
    active_events = await service.get_active_events(limit=10)
    audit_logs = await service.get_recent_audit_logs(limit=8)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "counters": counters,
            "active_events": active_events,
            "audit_logs": audit_logs,
            "admin": admin,
        },
    )
