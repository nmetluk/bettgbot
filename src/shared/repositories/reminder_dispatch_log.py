"""`ReminderDispatchLogRepository` — запись фактов отправки напоминаний (TASK-017)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReminderDispatchLog

__all__ = ["ReminderDispatchLogRepository"]


class ReminderDispatchLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def was_dispatched(self, *, user_id: int, event_id: int, offset_minutes: int) -> bool:
        stmt = select(ReminderDispatchLog.id).where(
            ReminderDispatchLog.user_id == user_id,
            ReminderDispatchLog.event_id == event_id,
            ReminderDispatchLog.offset_minutes == offset_minutes,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def record(self, *, user_id: int, event_id: int, offset_minutes: int) -> bool:
        """Возвращает True если вставка прошла, False если уже было (гонка).

        `on_conflict_do_nothing` защищает от двух одновременных вызовов из
        параллельных scheduler-инстансов (на MVP не сценарий, но дёшево).
        """
        stmt = (
            pg_insert(ReminderDispatchLog)
            .values(
                user_id=user_id,
                event_id=event_id,
                offset_minutes=offset_minutes,
            )
            .on_conflict_do_nothing(
                constraint="uq_reminder_dispatch_log_user_event_offset",
            )
            .returning(ReminderDispatchLog.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
