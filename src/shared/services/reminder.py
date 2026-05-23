"""`ReminderService` — настройка и поиск пользователей для напоминаний."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidReminderOffsetsError
from ..models import ReminderSetting
from ..repositories import ReminderSettingRepository

__all__ = ["ReminderService"]

_MAX_OFFSETS = 5
_MIN_OFFSET_MINUTES = 5


class ReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._reminders = ReminderSettingRepository(session)

    async def get(self, user_id: int) -> ReminderSetting | None:
        return await self._reminders.get_by_user(user_id)

    async def update(
        self, *, user_id: int, enabled: bool, offsets_minutes: list[int]
    ) -> ReminderSetting:
        self._validate_offsets(offsets_minutes)
        # UX: показываем от самого дальнего к самому близкому.
        sorted_offsets = sorted(set(offsets_minutes), reverse=True)
        rs = await self._reminders.upsert(
            user_id=user_id, enabled=enabled, offsets_minutes=sorted_offsets
        )
        await self._session.commit()
        return rs

    async def list_users_to_notify(self, *, offset_minutes: int) -> Sequence[int]:
        return await self._reminders.list_eligible_user_ids(offset_minutes=offset_minutes)

    @staticmethod
    def _validate_offsets(offsets: list[int]) -> None:
        if len(offsets) > _MAX_OFFSETS:
            raise InvalidReminderOffsetsError(
                f"too many offsets: {len(offsets)} (max {_MAX_OFFSETS})"
            )
        if len(set(offsets)) != len(offsets):
            raise InvalidReminderOffsetsError("duplicate offsets")
        for value in offsets:
            if value < _MIN_OFFSET_MINUTES:
                raise InvalidReminderOffsetsError(
                    f"offset {value} below minimum {_MIN_OFFSET_MINUTES}"
                )
