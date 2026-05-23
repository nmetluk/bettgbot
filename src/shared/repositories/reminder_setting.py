"""`ReminderSettingRepository` — запросы к таблице `reminder_setting`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReminderSetting

__all__ = ["ReminderSettingRepository"]


class ReminderSettingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(self, user_id: int) -> ReminderSetting | None:
        result = await self._session.execute(
            select(ReminderSetting).where(ReminderSetting.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, *, user_id: int, enabled: bool, offsets_minutes: list[int]
    ) -> ReminderSetting:
        stmt = (
            pg_insert(ReminderSetting)
            .values(
                user_id=user_id,
                enabled=enabled,
                offsets_minutes=offsets_minutes,
            )
            .on_conflict_do_update(
                index_elements=[ReminderSetting.user_id],
                set_={
                    "enabled": enabled,
                    "offsets_minutes": offsets_minutes,
                    "updated_at": func.now(),
                },
            )
            .returning(ReminderSetting)
        )
        result = await self._session.execute(stmt)
        obj = result.scalar_one()
        # См. PredictionRepository.upsert: identity_map может вернуть старый
        # экземпляр со стейтом до обновления.
        await self._session.refresh(obj)
        return obj

    async def list_eligible_user_ids(self, *, offset_minutes: int) -> Sequence[int]:
        # `:offset = ANY(offsets_minutes)` — поиск конкретного оффсета в массиве.
        # Pure-SQL форма проще, чем any_()/contains() через ORM, и явно типизирована.
        stmt = select(ReminderSetting.user_id).where(
            ReminderSetting.enabled.is_(True),
            text(":offset_minutes = ANY(reminder_setting.offsets_minutes)").bindparams(
                bindparam("offset_minutes", offset_minutes)
            ),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
