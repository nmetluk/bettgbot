"""`StatsService` — агрегированная статистика по прогнозам пользователя."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import PredictionRepository

__all__ = ["StatsService"]


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._predictions = PredictionRepository(session)

    async def user_stats(self, user_id: int) -> tuple[int, int, float]:
        """Возвращает `(correct, total, percent)`. `total` — только зафиксированные."""
        correct, total = await self._predictions.user_stats(user_id)
        percent = round(correct / total * 100, 1) if total else 0.0
        return correct, total, percent
