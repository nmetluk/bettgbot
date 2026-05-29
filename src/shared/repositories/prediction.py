"""`PredictionRepository` — запросы к таблице `prediction`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, cast, func, not_, select, update
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Event, Prediction, User

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

    async def count_24h(self) -> int:
        """Количество прогнозов за последние 24 часа."""
        cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
        stmt = select(func.count()).select_from(Prediction).where(Prediction.created_at >= cutoff)
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
                (User.first_name + " " + func.coalesce(User.last_name, "")).label(
                    "display_name"
                ),
                accuracy.label("accuracy"),
            )
            .join(User, Prediction.user_id == User.id)
            .where(User.is_blocked.is_(False))
        )

        if period_days is not None:
            cutoff = datetime.now(tz=UTC) - timedelta(days=period_days)
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
