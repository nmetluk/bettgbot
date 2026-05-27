"""`OutcomeRepository` — запросы к таблице `outcome`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Outcome

__all__ = ["OutcomeRepository"]


class OutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, outcome_id: int) -> Outcome | None:
        result = await self._session.execute(select(Outcome).where(Outcome.id == outcome_id))
        return result.scalar_one_or_none()

    async def list_by_event(self, event_id: int) -> Sequence[Outcome]:
        stmt = (
            select(Outcome)
            .where(Outcome.event_id == event_id)
            .order_by(Outcome.sort_order, Outcome.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_event(self, event_id: int) -> int:
        stmt = select(func.count()).select_from(Outcome).where(Outcome.event_id == event_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def create(self, *, event_id: int, label: str, sort_order: int = 0) -> Outcome:
        outcome = Outcome(event_id=event_id, label=label, sort_order=sort_order)
        self._session.add(outcome)
        await self._session.flush()
        return outcome

    async def update(self, outcome_id: int, event_id: int, **fields: Any) -> int:
        """Обновляет исход, если он принадлежит указанному событию.

        Returns:
            Количество затронутых строк (0 если outcome не найден или не принадлежит event).
        """
        if not fields:
            return 0
        result = await self._session.execute(
            update(Outcome)
            .where(Outcome.id == outcome_id, Outcome.event_id == event_id)
            .values(**fields)
        )
        return result.rowcount  # type: ignore[attr-defined,no-any-return]

    async def delete(self, outcome_id: int, event_id: int) -> int:
        """Удаляет исход, если он принадлежит указанному событию.

        Returns:
            Количество затронутых строк (0 если outcome не найден или не принадлежит event).
        """
        result = await self._session.execute(
            delete(Outcome).where(Outcome.id == outcome_id, Outcome.event_id == event_id)
        )
        return result.rowcount  # type: ignore[attr-defined,no-any-return]
