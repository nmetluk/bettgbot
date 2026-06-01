"""`PredictionRepository` — запросы к таблице `prediction`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, cast, func, not_, select, update
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Category, Event, Outcome, Prediction, User
from ..time import utcnow

__all__ = ["PredictionRepository"]


class PredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_event(self, user_id: int, event_id: int) -> Prediction | None:
        stmt = select(Prediction).where(
            and_(Prediction.user_id == user_id, Prediction.event_id == event_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, *, user_id: int, event_id: int, outcome_id: int) -> Prediction:
        stmt = (
            pg_insert(Prediction)
            .values(user_id=user_id, event_id=event_id, outcome_id=outcome_id)
            .on_conflict_do_update(
                constraint="uq_prediction_user_event",
                set_={"outcome_id": outcome_id, "updated_at": func.now()},
            )
            .returning(Prediction)
        )
        result = await self._session.execute(stmt)
        obj = result.scalar_one()
        # При повторном upsert identity_map может вернуть закэшированный экземпляр
        # со старыми значениями — обновим из БД.
        await self._session.refresh(obj)
        return obj

    async def list_active_by_user(
        self, user_id: int, *, offset: int = 0, limit: int = 20
    ) -> Sequence[Prediction]:
        stmt = (
            select(Prediction)
            .join(Event, Prediction.event_id == Event.id)
            .where(Prediction.user_id == user_id, Event.is_archived.is_(False))
            .order_by(Event.starts_at, Prediction.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_archived_by_user(
        self, user_id: int, *, offset: int = 0, limit: int = 20
    ) -> Sequence[Prediction]:
        stmt = (
            select(Prediction)
            .join(Event, Prediction.event_id == Event.id)
            .where(Prediction.user_id == user_id, Event.is_archived.is_(True))
            .order_by(Event.starts_at.desc(), Prediction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def mark_correctness(self, event_id: int, correct_outcome_id: int) -> int:
        stmt = (
            update(Prediction)
            .where(Prediction.event_id == event_id)
            .values(
                is_correct=case(
                    (Prediction.outcome_id == correct_outcome_id, True),
                    else_=False,
                )
            )
        )
        result = await self._session.execute(stmt)
        # session.execute(update(...)) фактически возвращает CursorResult; mypy
        # видит общий Result, поэтому игнорируем attr-defined для rowcount.
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def user_stats(self, user_id: int) -> tuple[int, int]:
        stmt = select(
            func.count().filter(Prediction.is_correct.is_(True)),
            func.count().filter(Prediction.is_correct.isnot(None)),
        ).where(Prediction.user_id == user_id)
        result = await self._session.execute(stmt)
        row = result.one()
        return int(row[0]), int(row[1])

    async def list_all_by_user_for_admin(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Prediction]:
        """Все прогнозы пользователя (active + archived) для админ-карточки.

        Сортировка `Event.starts_at DESC` — недавние/предстоящие наверху,
        старые ниже. Eager loads (`selectinload`):
        - `Prediction.event` (для title / is_archived / is_published / starts_at);
        - `Prediction.outcome` (для label выбора пользователя).
        """
        stmt = (
            select(Prediction)
            .join(Event, Prediction.event_id == Event.id)
            .options(
                selectinload(Prediction.event),
                selectinload(Prediction.outcome),
            )
            .where(Prediction.user_id == user_id)
            .order_by(Event.starts_at.desc(), Prediction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def users_without_prediction_for_event(self, event_id: int) -> Sequence[int]:
        existing = select(Prediction.user_id).where(Prediction.event_id == event_id)
        stmt = (
            select(User.id)
            .where(User.is_blocked.is_(False), not_(User.id.in_(existing)))
            .order_by(User.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Общее количество прогнозов."""
        stmt = select(func.count()).select_from(Prediction)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_for_event(self, event_id: int) -> int:
        """Количество прогнозов по конкретному событию."""
        stmt = select(func.count()).select_from(Prediction).where(Prediction.event_id == event_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_24h(self) -> int:
        """Количество прогнозов за последние 24 часа."""
        cutoff = utcnow() - timedelta(hours=24)
        return await self.count_predictions_since(cutoff)

    async def count_predictions_since(self, since: datetime) -> int:
        """Количество прогнозов с указанного момента (для дельт в админ-дайджесте TASK-098)."""
        stmt = select(func.count()).select_from(Prediction).where(Prediction.created_at >= since)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def leaderboard(
        self,
        *,
        min_resolved: int = 5,
        limit: int = 100,
        period_days: int | None = None,
    ) -> Sequence[tuple[int, int, int, str, float]]:
        """Рейтинг пользователей по точности прогнозов.

        Возвращает список кортежей ``(user_id, correct, resolved, display_name, accuracy)``.
        Сортировка: по точности ↓, затем ``correct`` ↓, затем ``resolved`` ↓.
        Пользователи с ``resolved < min_resolved`` исключены (``HAVING``).
        Заблокированные (``is_blocked``) исключены.

        Args:
            min_resolved: Минимальное количество разрешённых прогнозов для попадания в рейтинг.
            limit: Максимальное количество строк в результате.
            period_days: Фильтр по количеству дней (``None`` = all-time).
        """
        correct = func.count().filter(Prediction.is_correct.is_(True))
        resolved = func.count().filter(Prediction.is_correct.isnot(None))
        accuracy = func.round(
            cast(correct, NUMERIC) / cast(resolved, NUMERIC) * 100,
            1,
        )

        stmt = (
            select(
                Prediction.user_id,
                correct.label("correct"),
                resolved.label("resolved"),
                (User.first_name + " " + func.coalesce(User.last_name, "")).label("display_name"),
                accuracy.label("accuracy"),
            )
            .join(User, Prediction.user_id == User.id)
            .where(User.is_blocked.is_(False))
        )

        if period_days is not None:
            cutoff = utcnow() - timedelta(days=period_days)
            stmt = stmt.where(Prediction.created_at >= cutoff)

        stmt = (
            stmt.group_by(Prediction.user_id, User.first_name, User.last_name)
            .having(resolved >= min_resolved)
            .order_by(accuracy.desc(), correct.desc(), resolved.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        rows: list[tuple[int, int, int, str, float]] = []
        for row in result:
            rows.append(
                (
                    int(row.user_id),
                    int(row.correct),
                    int(row.resolved),
                    str(row.display_name),
                    float(row.accuracy),
                )
            )
        return rows

    async def daily_prediction_counts(self, *, days: int = 30) -> Sequence[tuple[str, int]]:
        """Подсчёт прогнозов по дням за последние N дней.

        Возвращает список кортежей ``(date_str, count)`` где ``date_str`` —
        формат ``YYYY-MM-DD``. Дни без прогнозов не включаются в результат
        (заполняются нулями на уровне сервиса).
        """
        cutoff = utcnow() - timedelta(days=days)
        stmt = (
            select(
                func.date(Prediction.created_at).label("day"),
                func.count().label("count"),
            )
            .where(Prediction.created_at >= cutoff)
            .group_by(func.date(Prediction.created_at))
            .order_by(func.date(Prediction.created_at))
        )
        result = await self._session.execute(stmt)
        return [(str(row.day), int(row.count)) for row in result]  # type: ignore[call-overload]

    async def category_accuracy(self) -> Sequence[tuple[int, str, str, int, int, float | None]]:
        """Точность прогнозов по категориям.

        Возвращает список кортежей ``(category_id, category_name, category_slug,
        correct, resolved, accuracy)``. ``accuracy`` — ``None`` если ``resolved == 0``.
        Категории без разрешённых прогнозов исключаются.
        """
        correct = func.count().filter(Prediction.is_correct.is_(True))
        resolved = func.count().filter(Prediction.is_correct.isnot(None))
        accuracy = func.round(
            cast(correct, NUMERIC) / cast(resolved, NUMERIC) * 100,
            1,
        )

        stmt = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                Category.slug.label("category_slug"),
                correct.label("correct"),
                resolved.label("resolved"),
                accuracy.label("accuracy"),
            )
            .join(Event, Event.category_id == Category.id)
            .join(Prediction, Prediction.event_id == Event.id)
            .group_by(Category.id, Category.name, Category.slug)
            .having(resolved > 0)
            .order_by(Category.sort_order, Category.name)
        )
        result = await self._session.execute(stmt)
        return [
            (
                int(row.category_id),
                str(row.category_name),
                str(row.category_slug),
                int(row.correct),
                int(row.resolved),
                float(row.accuracy) if row.accuracy is not None else None,
            )
            for row in result
        ]

    async def funnel_metrics(self) -> tuple[int, int]:
        """Метрики воронки «регистрация → первый прогноз».

        Возвращает ``(total_users, users_with_predictions)`` где:
        - ``total_users`` — количество незаблокированных пользователей;
        - ``users_with_predictions`` — количество пользователей с ≥1 прогнозом.
        """
        total_stmt = select(func.count()).select_from(User).where(User.is_blocked.is_(False))
        total_result = await self._session.execute(total_stmt)
        total = int(total_result.scalar_one())

        with_pred_stmt = (
            select(func.count(User.id).distinct())
            .join(Prediction, Prediction.user_id == User.id)
            .where(User.is_blocked.is_(False))
        )
        with_pred_result = await self._session.execute(with_pred_stmt)
        with_pred = int(with_pred_result.scalar_one())

        return total, with_pred

    async def count_new_and_converted_since(self, since: datetime) -> tuple[int, int]:
        """(new_users_since, new_users_with_>=1_prediction) для конверсии новых в админ-дайджесте (TASK-098).

        Только незаблокированные. Прогнозы — за всё время.
        """
        new_stmt = select(func.count()).select_from(User).where(
            User.created_at >= since, User.is_blocked.is_(False)
        )
        new_result = await self._session.execute(new_stmt)
        new_count = int(new_result.scalar_one())

        converted_stmt = (
            select(func.count(User.id).distinct())
            .join(Prediction, Prediction.user_id == User.id)
            .where(User.created_at >= since, User.is_blocked.is_(False))
        )
        converted_result = await self._session.execute(converted_stmt)
        converted_count = int(converted_result.scalar_one())
        return new_count, converted_count

    async def top_events(self, *, limit: int = 10) -> Sequence[tuple[int, str, str, int]]:
        """Топ событий по количеству прогнозов.

        Возвращает список кортежей ``(event_id, event_title, category_slug,
        prediction_count)`` отсортированный по количеству прогнозов (убывание).
        """
        stmt = (
            select(
                Event.id.label("event_id"),
                Event.title.label("event_title"),
                Category.slug.label("category_slug"),
                func.count(Prediction.id).label("prediction_count"),
            )
            .join(Category, Category.id == Event.category_id)
            .join(Prediction, Prediction.event_id == Event.id)
            .group_by(Event.id, Event.title, Category.slug)
            .order_by(func.count(Prediction.id).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            (
                int(row.event_id),
                str(row.event_title),
                str(row.category_slug),
                int(row.prediction_count),
            )
            for row in result
        ]

    async def top_events_in_window(
        self, *, since: datetime, limit: int = 3
    ) -> list[tuple[str, int]]:
        """Топ событий по числу прогнозов в окне времени (для админ-дайджеста TASK-098).

        Возвращает [(title, count), ...] по убыванию. Без category, т.к. в дайджесте только title + N.
        """
        stmt = (
            select(
                Event.title.label("event_title"),
                func.count(Prediction.id).label("prediction_count"),
            )
            .join(Prediction, Prediction.event_id == Event.id)
            .where(Prediction.created_at >= since)
            .group_by(Event.id, Event.title)
            .order_by(func.count(Prediction.id).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(str(row.event_title), int(row.prediction_count)) for row in result]

    async def outcome_distribution_for_event(self, event_id: int) -> list[tuple[int, str, int]]:
        """Распределение прогнозов по исходам события: [(outcome_id, label, count), ...] sorted by count desc."""
        stmt = (
            select(
                Outcome.id.label("outcome_id"),
                Outcome.label.label("label"),
                func.count(Prediction.id).label("cnt"),
            )
            .join(Prediction, Prediction.outcome_id == Outcome.id)
            .where(Prediction.event_id == event_id)
            .group_by(Outcome.id, Outcome.label)
            .order_by(func.count(Prediction.id).desc(), Outcome.id)
        )
        result = await self._session.execute(stmt)
        return [(int(row.outcome_id), str(row.label), int(row.cnt)) for row in result]

    async def prediction_accuracy_for_events_closed_since(
        self, since: datetime
    ) -> tuple[int, int] | None:
        """(correct, total) прогнозов по событиям, закрытым (archived_at >= since) за окно.

        Используется для точности закрытых событий в админ-дайджесте (TASK-098).
        Возвращает None если нет таких событий (чтобы отличить от 0/0).
        """
        from src.shared.models import Event

        stmt = (
            select(
                func.sum(case((Prediction.is_correct.is_(True), 1), else_=0)).label("correct"),
                func.count(Prediction.id).label("total"),
            )
            .join(Event, Event.id == Prediction.event_id)
            .where(Event.archived_at >= since)
        )
        result = await self._session.execute(stmt)
        row = result.one()
        correct = int(row.correct or 0)
        total = int(row.total or 0)
        if total == 0:
            return None
        return correct, total

    async def correct_users_for_event(self, event_id: int) -> list[dict[str, Any]]:
        """Список угадавших пользователей (для CSV и текстовой сводки).

        Поля: tg_user_id, first_name, last_name, tg_username, phone, outcome_label, predicted_at.
        Сортировка по user_id (стабильная).
        """
        stmt = (
            select(
                User.tg_user_id,
                User.first_name,
                User.last_name,
                User.tg_username,
                User.phone,
                Outcome.label.label("outcome_label"),
                Prediction.created_at.label("predicted_at"),
            )
            .join(User, Prediction.user_id == User.id)
            .join(Outcome, Prediction.outcome_id == Outcome.id)
            .where(
                Prediction.event_id == event_id,
                Prediction.is_correct.is_(True),
            )
            .order_by(User.id)
        )
        result = await self._session.execute(stmt)
        return [
            {
                "tg_user_id": int(row.tg_user_id),
                "first_name": row.first_name,
                "last_name": row.last_name,
                "tg_username": row.tg_username,
                "phone": row.phone,
                "outcome_label": row.outcome_label,
                "predicted_at": row.predicted_at,
            }
            for row in result
        ]
