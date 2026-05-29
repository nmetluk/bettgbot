"""Routes раздела «Аналитика и статистика» админки (TASK-059)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.app import templates
from src.admin.deps import current_admin
from src.shared.db import SessionLocal
from src.shared.models import AdminUser
from src.shared.services import StatsService

__all__ = ["router"]


router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("", response_class=HTMLResponse)
async def analytics(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """Экран «Аналитика и статистика» с четырьмя метриками."""
    service = StatsService(session)

    daily_counts = await service.daily_prediction_counts(days=30)
    category_accuracy = await service.category_accuracy()
    funnel = await service.funnel_metrics()
    top_events = await service.top_events(limit=10)

    # Конвертируем dataclass'ы в dict для JSON-сериализации в шаблоне
    return templates.TemplateResponse(
        request=request,
        name="analytics/list.html",
        context={
            "admin": admin,
            "daily_counts": [asdict(row) for row in daily_counts],
            "category_accuracy": [asdict(row) for row in category_accuracy],
            "funnel": asdict(funnel),
            "top_events": [asdict(row) for row in top_events],
        },
    )
