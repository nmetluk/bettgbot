"""`DashboardService` — счётчики для главной страницы админки."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import (
    CategoryRepository,
    EventRepository,
    PredictionRepository,
    UserRepository,
)

__all__ = ["DashboardService"]


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._events = EventRepository(session)
        self._categories = CategoryRepository(session)
        self._predictions = PredictionRepository(session)

    async def get_counters(self) -> dict[str, int]:
        """Счётчики объектов в БД для главной страницы админки.

        Все счётчики возвращают total без фильтров — админу нужна полная
        картина системы, а не «видимое из бота» подмножество.

        Returns:
            dict с ключами:
              - users — все пользователи, включая заблокированных
                (`is_blocked=true`). Удалённых нет — soft-delete не реализован.
              - events — все события, включая черновики (`is_published=false`)
                и архивные (`is_archived=true`).
              - categories — все категории, включая неактивные (`is_active=false`).
              - predictions — все прогнозы, в т.ч. по архивным событиям.

        Note:
            Запросы выполняются последовательно (4 простых COUNT-а). См.
            `state/DECISIONS.md` от 2026-05-26 — concurrent ops на одной
            AsyncSession в SQLAlchemy запрещены.
        """
        users = await self._users.count_for_admin()
        events = await self._events.count_for_admin()  # status="all" by default
        categories = await self._categories.count()  # include_inactive=True by default
        predictions = await self._predictions.count()
        return {
            "users": users,
            "events": events,
            "categories": categories,
            "predictions": predictions,
        }
