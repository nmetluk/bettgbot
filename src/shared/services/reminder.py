"""`ReminderService` — настройка и поиск пользователей для напоминаний."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidReminderOffsetsError
from ..models import Event, Prediction, ReminderDispatchLog, ReminderSetting, User
from ..repositories import ReminderSettingRepository

__all__ = ["ReminderCandidate", "ReminderService"]

_MAX_OFFSETS = 5
_MIN_OFFSET_MINUTES = 5


@dataclass(frozen=True, slots=True)
class ReminderCandidate:
    """Кандидат на отправку напоминания: один user × event × offset."""

    tg_user_id: int
    user_id: int
    event_id: int
    event_title: str
    offset_minutes: int
    predictions_close_at: datetime


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

    async def find_candidates(
        self, *, now: datetime, window_minutes: int = 10
    ) -> list[ReminderCandidate]:
        """Кандидаты на отправку напоминания в текущем тике scheduler'а.

        Окно: для каждого `offset` берём события, у которых
        `now + offset <= predictions_close_at < now + offset + window_minutes`.

        Пример: `now = 12:00`, `event.predictions_close_at = 13:02`, `offset = 60`,
        `window_minutes = 5`. Разница 62 мин, окно `[60, 65)` — кандидат подходит.

        Фильтры:
        - событие `is_published` И НЕ `is_archived`,
        - пользователь НЕ заблокирован,
        - `reminder_setting.enabled` И в `offsets_minutes` есть подходящий offset,
        - нет `prediction` для (user, event),
        - нет `reminder_dispatch_log` для (user, event, offset).
        """
        # unnest(offsets_minutes) разворачивает массив в строки: один user × N offset.
        offset_col = func.unnest(ReminderSetting.offsets_minutes).label("offset_minutes")
        settings_unnested = (
            select(
                ReminderSetting.user_id.label("user_id"),
                offset_col,
            )
            .where(ReminderSetting.enabled.is_(True))
            .subquery()
        )

        # EXTRACT EPOCH даёт секунды; /60 — минуты до дедлайна (float).
        diff_minutes = func.extract("EPOCH", Event.predictions_close_at - now) / 60.0

        stmt = (
            select(
                User.tg_user_id,
                User.id,
                Event.id.label("event_id"),
                Event.title,
                settings_unnested.c.offset_minutes,
                Event.predictions_close_at,
            )
            .select_from(settings_unnested)
            .join(User, User.id == settings_unnested.c.user_id)
            .join(
                Event,
                Event.is_published.is_(True) & Event.is_archived.is_(False),
            )
            .outerjoin(
                Prediction,
                (Prediction.user_id == settings_unnested.c.user_id)
                & (Prediction.event_id == Event.id),
            )
            .outerjoin(
                ReminderDispatchLog,
                (ReminderDispatchLog.user_id == settings_unnested.c.user_id)
                & (ReminderDispatchLog.event_id == Event.id)
                & (ReminderDispatchLog.offset_minutes == settings_unnested.c.offset_minutes),
            )
            .where(
                User.is_blocked.is_(False),
                diff_minutes >= settings_unnested.c.offset_minutes,
                diff_minutes < settings_unnested.c.offset_minutes + window_minutes,
                Prediction.id.is_(None),
                ReminderDispatchLog.id.is_(None),
            )
        )

        result = await self._session.execute(stmt)
        return [
            ReminderCandidate(
                tg_user_id=row.tg_user_id,
                user_id=row.id,
                event_id=row.event_id,
                event_title=row.title,
                offset_minutes=row.offset_minutes,
                predictions_close_at=row.predictions_close_at,
            )
            for row in result
        ]

    @staticmethod
    def _validate_offsets(offsets: list[int]) -> None:
        if len(offsets) > _MAX_OFFSETS:
            raise InvalidReminderOffsetsError(
                f"too many offsets: {len(offsets)} (max {_MAX_OFFSETS})",
                reason="too_many",
            )
        if len(set(offsets)) != len(offsets):
            raise InvalidReminderOffsetsError("duplicate offsets", reason="duplicate")
        for value in offsets:
            if value < _MIN_OFFSET_MINUTES:
                raise InvalidReminderOffsetsError(
                    f"offset {value} below minimum {_MIN_OFFSET_MINUTES}",
                    reason="below_minimum",
                )
