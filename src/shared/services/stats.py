"""`StatsService` — агрегированная статистика по прогнозам пользователя."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import PredictionRepository

__all__ = ["LeaderboardRow", "StatsService"]


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    """Строка рейтинга пользователей."""

    rank: int
    user_id: int
    display_name: str
    correct: int
    resolved: int
    accuracy: float


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._predictions = PredictionRepository(session)

    async def user_stats(self, user_id: int) -> tuple[int, int, float]:
        """Возвращает `(correct, total, percent)`. `total` — только зафиксированные."""
        correct, total = await self._predictions.user_stats(user_id)
        percent = round(correct / total * 100, 1) if total else 0.0
        return correct, total, percent

    async def leaderboard(
        self,
        *,
        min_resolved: int = 5,
        limit: int = 100,
        period_days: int | None = None,
    ) -> list[LeaderboardRow]:
        """Рейтинг пользователей по точности прогнозов.

        Args:
            min_resolved: Минимальное количество разрешённых прогнозов для попадания в рейтинг.
            limit: Максимальное количество строк в результате.
            period_days: Фильтр по количеству дней (``None`` = all-time, ``30`` = 30 дней).

        Returns:
            Список ``LeaderboardRow`` отсортированный по точности (убывание),
            затем количеству верных, затем количеству разрешённых.
        """
        rows = await self._predictions.leaderboard(
            min_resolved=min_resolved, limit=limit, period_days=period_days
        )
        result: list[LeaderboardRow] = []
        for rank, (user_id, correct, resolved, display_name, accuracy) in enumerate(rows, start=1):
            result.append(
                LeaderboardRow(
                    rank=rank,
                    user_id=user_id,
                    display_name=display_name,
                    correct=correct,
                    resolved=resolved,
                    accuracy=accuracy,
                )
            )
        return result
