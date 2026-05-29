"""`DashboardService` — счётчики для главной страницы админки."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    AuditLogRepository,
    CategoryRepository,
    EventRepository,
    PredictionRepository,
    UserRepository,
)

__all__ = ["ActiveEventInfo", "AuditLogInfo", "DashboardService"]


@dataclass(frozen=True)
class ActiveEventInfo:
    """Информация об активном событии для дашборда."""

    id: int
    title: str
    category_id: int | None
    category_name: str | None
    starts_at: datetime
    predictions_count: int
    status: str  # "open" или "closed"


@dataclass(frozen=True)
class AuditLogInfo:
    """Информация о записи аудита для дашборда."""

    id: int
    admin_username: str
    action: str
    created_at: datetime


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._events = EventRepository(session)
        self._categories = CategoryRepository(session)
        self._predictions = PredictionRepository(session)
        self._audit = AuditLogRepository(session)

    async def get_counters(self) -> dict[str, int | dict[str, int]]:
        """Счётчики объектов в БД для главной страницы админки.

        Все счётчики возвращают total без фильтров — админу нужна полная
        картина системы, а не «видимое из бота» подмножество.

        Returns:
            dict с ключами:
              - users_total — все пользователи, включая заблокированных
              - users_active_30d — пользователи с last_seen_at за 30 дней
              - predictions_total — все прогнозы, в т.ч. по архивным событиям
              - predictions_24h — прогнозы за последние 24 часа
              - events_total — все события (черновики + опубликованные + архивные)
              - events_published — опубликованные события (не архивные)
              - events_archived — архивные события
              - categories — все категории, включая неактивные
              - categories_hidden — категории, скрытые от бота (is_active=false)

        Note:
            Запросы выполняются последовательно (несколько COUNT-запросов). См.
            `state/DECISIONS.md` от 2026-05-26 — concurrent ops на одной
            AsyncSession в SQLAlchemy запрещены.
        """
        users_total = await self._users.count_for_admin()
        users_active_30d = await self._users.count_active_30d()
        predictions_total = await self._predictions.count()
        predictions_24h = await self._predictions.count_24h()
        events_total = await self._events.count_for_admin()  # status="all"
        events_published = await self._events.count_for_admin(
            status="published_open"
        ) + await self._events.count_for_admin(status="published_closed")
        events_archived = await self._events.count_for_admin(status="archived")
        categories_total = await self._categories.count()
        categories_active = await self._categories.count(include_inactive=False)
        categories_hidden = categories_total - categories_active

        return {
            "users_total": users_total,
            "users_active_30d": users_active_30d,
            "predictions_total": predictions_total,
            "predictions_24h": predictions_24h,
            "events_total": events_total,
            "events_published": events_published,
            "events_archived": events_archived,
            "categories": categories_total,
            "categories_hidden": categories_hidden,
        }

    async def get_active_events(self, *, limit: int = 10) -> Sequence[ActiveEventInfo]:
        """Активные события (open/closed) с количеством прогнозов.

        Активные — это опубликованные неархивные события (status=open или closed).
        Возвращает события с подсчётом прогнозов, отсортированные по starts_at DESC.
        """
        events_with_counts = await self._events.list_for_admin_with_predictions_count(
            status="published_open", offset=0, limit=limit
        )
        open_events = [
            ActiveEventInfo(
                id=e.id,
                title=e.title,
                category_id=e.category_id,
                category_name=e.category.name if e.category else None,
                starts_at=e.starts_at,
                predictions_count=count,
                status="open",
            )
            for e, count in events_with_counts
        ]

        closed_events = await self._events.list_for_admin_with_predictions_count(
            status="published_closed", offset=0, limit=limit
        )
        closed = [
            ActiveEventInfo(
                id=e.id,
                title=e.title,
                category_id=e.category_id,
                category_name=e.category.name if e.category else None,
                starts_at=e.starts_at,
                predictions_count=count,
                status="closed",
            )
            for e, count in closed_events
        ]

        # Объединить и отсортировать по starts_at DESC
        all_active = sorted(open_events + closed, key=lambda x: x.starts_at, reverse=True)
        return all_active[:limit]

    async def get_recent_audit_logs(self, *, limit: int = 8) -> Sequence[AuditLogInfo]:
        """Последние записи аудита для дашборда."""
        logs = await self._audit.list(offset=0, limit=limit)
        return [
            AuditLogInfo(
                id=log.id,
                admin_username=log.admin.login if log.admin else "?",
                action=log.action,
                created_at=log.created_at,
            )
            for log in logs
        ]
