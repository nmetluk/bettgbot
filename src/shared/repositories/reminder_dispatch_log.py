"""`ReminderDispatchLogRepository` — запись фактов отправки напоминаний (TASK-017)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
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

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Удаляет записи старше cutoff для cleanup job'а (TASK-048).

        Возвращает количество удалённых строк.
        """
        stmt = delete(ReminderDispatchLog).where(ReminderDispatchLog.dispatched_at < cutoff)
        result = await self._session.execute(stmt)
        return result.rowcount
