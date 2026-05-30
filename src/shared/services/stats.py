"""`StatsService` — агрегированная статистика по прогнозам пользователя."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import PredictionRepository
from ..time import utcnow

__all__ = [
    "AnalyticsDayRow",
    "AnalyticsFunnelMetrics",
    "AnalyticsTopEventRow",
    "CategoryAccuracyRow",
    "LeaderboardRow",
    "StatsService",
]


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    """Строка рейтинга пользователей."""

    rank: int
    user_id: int
    display_name: str
    correct: int
    resolved: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class CategoryAccuracyRow:
    """Точность прогнозов по категории."""

    category_id: int
    category_name: str
    category_slug: str
    correct: int
    resolved: int
    accuracy: float | None


@dataclass(frozen=True, slots=True)
class AnalyticsDayRow:
    """Строка динамики прогнозов по дням."""

    date: str  # YYYY-MM-DD
    count: int


@dataclass(frozen=True, slots=True)
class AnalyticsFunnelMetrics:
    """Метрики воронки «регистрация → первый прогноз»."""

    total_users: int
    users_with_predictions: int
    conversion_percent: float


@dataclass(frozen=True, slots=True)
class AnalyticsTopEventRow:
    """Строка топ-событий по числу прогнозов."""

    event_id: int
    event_title: str
    category_slug: str
    prediction_count: int


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

    async def daily_prediction_counts(self, *, days: int = 30) -> list[AnalyticsDayRow]:
        """Динамика прогнозов по дням за последние N дней.

        Дни без прогнозов заполняются нулями для ровного ряда графика.
        """
        raw_rows = await self._predictions.daily_prediction_counts(days=days)

        # Строим полный диапазон дат и заполняем пропуски нулями.
        result: list[AnalyticsDayRow] = []
        raw_by_date: dict[str, int] = dict(raw_rows)

        for i in range(days):
            date = utcnow() - timedelta(days=days - 1 - i)
            date_str = date.strftime("%Y-%m-%d")
            count = raw_by_date.get(date_str, 0)
            result.append(AnalyticsDayRow(date=date_str, count=count))

        return result

    async def category_accuracy(self) -> list[CategoryAccuracyRow]:
        """Точность прогнозов по категориям."""
        rows = await self._predictions.category_accuracy()
        return [
            CategoryAccuracyRow(
                category_id=cat_id,
                category_name=name,
                category_slug=slug,
                correct=correct,
                resolved=resolved,
                accuracy=acc,
            )
            for cat_id, name, slug, correct, resolved, acc in rows
        ]

    async def funnel_metrics(self) -> AnalyticsFunnelMetrics:
        """Метрики воронки «регистрация → первый прогноз»."""
        total, with_pred = await self._predictions.funnel_metrics()
        conversion = round(with_pred / total * 100, 1) if total else 0.0
        return AnalyticsFunnelMetrics(
            total_users=total,
            users_with_predictions=with_pred,
            conversion_percent=conversion,
        )

    async def top_events(self, *, limit: int = 10) -> list[AnalyticsTopEventRow]:
        """Топ событий по количеству прогнозов."""
        rows = await self._predictions.top_events(limit=limit)
        return [
            AnalyticsTopEventRow(
                event_id=event_id,
                event_title=title,
                category_slug=slug,
                prediction_count=count,
            )
            for event_id, title, slug, count in rows
        ]
