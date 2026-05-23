"""`PredictionRepository` — запросы к таблице `prediction`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, case, func, not_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def users_without_prediction_for_event(self, event_id: int) -> Sequence[int]:
        existing = select(Prediction.user_id).where(Prediction.event_id == event_id)
        stmt = (
            select(User.id)
            .where(User.is_blocked.is_(False), not_(User.id.in_(existing)))
            .order_by(User.id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
