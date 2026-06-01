"""`StatsService` — агрегированная статистика по прогнозам пользователя."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import EventRepository, PredictionRepository, UserRepository
from ..time import utcnow

__all__ = [
    "AnalyticsDayRow",
    "AnalyticsFunnelMetrics",
    "AnalyticsTopEventRow",
    "CategoryAccuracyRow",
    "CorrectUserRow",
    "DailyAdminDigest",
    "EventResultSummary",
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


@dataclass(frozen=True, slots=True)
class CorrectUserRow:
    """Строка угадавшего пользователя для пост-итоговой сводки/CSV (TASK-097)."""

    tg_user_id: int
    first_name: str
    last_name: str | None
    tg_username: str | None
    phone: str
    outcome_label: str
    predicted_at: datetime


@dataclass(frozen=True, slots=True)
class EventResultSummary:
    """Сводка по итогам события для админ-уведомления (TASK-097 + 098)."""

    total_predictions: int
    correct_count: int
    # (outcome_id, label, count, is_winner)
    outcome_distribution: list[tuple[int, str, int, bool]]
    correct_users: list[CorrectUserRow]
    # TASK-098: самый популярный исход совпал с верным?
    majority_correct: bool | None
    # % участия = total_predictions / total_users (на момент)
    participation_pct: float | None


@dataclass(frozen=True, slots=True)
class DailyAdminDigest:
    """Обогащённый дневной дайджест для рассылки админам (TASK-098)."""

    total_users: int
    new_24h: int
    preds_24h: int
    new_24h_delta: int  # положительная — рост, отрицательная — спад, 0 — без изменений
    preds_24h_delta: int
    dau_24h: int
    active_events_now: int
    # [(title, count), ...] до 3, может быть пусто
    top_events_24h: list[tuple[str, int]]
    # Для закрытых событий за 24ч: если есть — correct, total, pct; иначе None
    closed_correct: int | None
    closed_total: int | None
    closed_accuracy_pct: float | None
    # Конверсия новых: converted, total_new, pct ; None если new==0
    converted_new: int | None
    total_new_for_conv: int | None
    conversion_pct: float | None


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._predictions = PredictionRepository(session)
        self._events = EventRepository(session)
        self._users = UserRepository(session)

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

    async def event_result_summary(self, event_id: int) -> EventResultSummary:
        """Пост-итоговая сводка события для рассылки админам (TASK-097).

        total + correct из прогнозов; распределение + список угадавших из PredictionRepo.
        is_winner — по текущему result_outcome_id события (может быть None если race).
        """
        total_predictions = await self._predictions.count_for_event(event_id)

        # Winner outcome (для флага is_winner в распределении)
        event = await self._events.get_by_id(event_id)
        winner_id = event.result_outcome_id if event else None

        dist_raw = await self._predictions.outcome_distribution_for_event(event_id)
        outcome_distribution: list[tuple[int, str, int, bool]] = []
        for oid, label, cnt in dist_raw:
            is_winner = oid == winner_id
            outcome_distribution.append((oid, label, cnt, is_winner))

        # Correct users (и count из длины списка — надёжнее, чем отдельный COUNT с is_correct)
        correct_raw = await self._predictions.correct_users_for_event(event_id)
        correct_users = [
            CorrectUserRow(
                tg_user_id=r["tg_user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                tg_username=r["tg_username"],
                phone=r["phone"],
                outcome_label=r["outcome_label"],
                predicted_at=r["predicted_at"],
            )
            for r in correct_raw
        ]
        correct_count = len(correct_users)

        # TASK-098: majority vs winner
        majority_correct: bool | None = None
        if outcome_distribution:
            _, _, _, max_is_win = max(outcome_distribution, key=lambda x: x[2])
            # если несколько с max, берём первый; проверяем его is_winner
            majority_correct = max_is_win

        # Participation
        total_users = await self._users.count_for_admin(query=None)
        participation_pct: float | None = None
        if total_users > 0 and total_predictions > 0:
            participation_pct = round((total_predictions / total_users * 100), 1)

        return EventResultSummary(
            total_predictions=total_predictions,
            correct_count=correct_count,
            outcome_distribution=outcome_distribution,
            correct_users=correct_users,
            majority_correct=majority_correct,
            participation_pct=participation_pct,
        )

    async def daily_admin_digest(self) -> DailyAdminDigest:
        """Обогащённая статистика для дневного дайджеста админам (TASK-098).

        Все окна — последние 24ч (и предыдущие 24ч для дельт).
        Логика подсчётов здесь (а не в джобе).
        """
        now = utcnow()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_48h = now - timedelta(hours=48)

        # Базовые из TASK-097
        total_users = await self._users.count_for_admin(query=None)
        new_24h = await self._users.count_new_since(cutoff_24h)
        preds_24h = await self._predictions.count_predictions_since(cutoff_24h)

        # Дельты к предыдущему окну
        new_up_to_48h = await self._users.count_new_since(cutoff_48h)
        new_prev_window = new_up_to_48h - new_24h
        new_delta = new_24h - new_prev_window

        preds_up_to_48h = await self._predictions.count_predictions_since(cutoff_48h)
        preds_prev_window = preds_up_to_48h - preds_24h
        preds_delta = preds_24h - preds_prev_window

        # DAU
        dau_24h = await self._users.count_active_since(cutoff_24h)

        # Активные события сейчас
        active_events = await self._events.count_currently_open()

        # Топ-3 по активности за 24ч
        top_events = await self._predictions.top_events_in_window(since=cutoff_24h, limit=3)

        # Точность закрытых за 24ч
        closed_stats = await self._predictions.prediction_accuracy_for_events_closed_since(
            cutoff_24h
        )
        if closed_stats is None:
            closed_correct = closed_total = closed_pct = None
        else:
            closed_correct, closed_total = closed_stats
            closed_pct = round((closed_correct / closed_total * 100), 1) if closed_total else None

        # Конверсия новых
        new_total, converted = await self._predictions.count_new_and_converted_since(cutoff_24h)
        if new_total == 0:
            conv_converted = conv_total = conv_pct = None
        else:
            conv_converted = converted
            conv_total = new_total
            conv_pct = round((conv_converted / conv_total * 100), 1)

        return DailyAdminDigest(
            total_users=total_users,
            new_24h=new_24h,
            preds_24h=preds_24h,
            new_24h_delta=new_delta,
            preds_24h_delta=preds_delta,
            dau_24h=dau_24h,
            active_events_now=active_events,
            top_events_24h=top_events,
            closed_correct=closed_correct,
            closed_total=closed_total,
            closed_accuracy_pct=closed_pct,
            converted_new=conv_converted,
            total_new_for_conv=conv_total,
            conversion_pct=conv_pct,
        )
