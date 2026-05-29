"""Routes раздела «Рейтинг» админки (TASK-058)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.models import AdminUser
from src.shared.services import StatsService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

PERIOD_CHOICES = {"all": None, "30d": 30, "90d": 90}


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("", response_class=HTMLResponse)
async def leaderboard(
    request: Request,
    period: str | None = Query(None, pattern="^(all|30d|90d)$"),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """Рейтинг пользователей по точности прогнозов."""
    period_days = PERIOD_CHOICES.get(period) if period else None
    service = StatsService(session)
    rows = await service.leaderboard(min_resolved=5, limit=100, period_days=period_days)
    return templates.TemplateResponse(
        request=request,
        name="leaderboard/list.html",
        context={
            "admin": admin,
            "rows": rows,
            "period": period or "all",
        },
    )
