"""`DashboardService` — счётчики для главной страницы админки."""

from __future__ import annotations

import asyncio

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
        """Возвращает счётчики для дашборда.

        Returns:
            Словарь с ключами: `users`, `events`, `categories`, `predictions`.
        """
        users, events, categories, predictions = await asyncio.gather(
            self._users.count_for_admin(),
            self._events.count_for_admin(),
            self._categories.count(),
            self._predictions.count(),
        )
        return {
            "users": users,
            "events": events,
            "categories": categories,
            "predictions": predictions,
        }
