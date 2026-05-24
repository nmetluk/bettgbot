"""Реализации scheduler-job'ов."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.logging import get_logger
from src.shared.repositories import ReminderDispatchLogRepository
from src.shared.services import ReminderService

from .. import keyboards, texts

__all__ = ["dispatch_reminders"]


logger = get_logger(__name__)


async def dispatch_reminders(*, bot: Bot, session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Один тик scheduler'а: найти кандидатов и отправить им сообщения.

    Идемпотентность: `dispatch_log.record(...)` зовётся ДО `send_message`.
    Если запись не прошла (гонка) — пропускаем. Если send_message упал
    (TelegramAPIError, юзер заблокировал бота) — лог не откатываем:
    повторно слать уже бессмысленно, момент прошёл.
    """
    now = datetime.now(tz=UTC)
    async with session_maker() as session:
        service = ReminderService(session)
        candidates = await service.find_candidates(now=now, window_minutes=5)
        dispatch_log = ReminderDispatchLogRepository(session)

        for cand in candidates:
            recorded = await dispatch_log.record(
                user_id=cand.user_id,
                event_id=cand.event_id,
                offset_minutes=cand.offset_minutes,
            )
            if not recorded:
                continue

            try:
                await bot.send_message(
                    cand.tg_user_id,
                    texts.REMINDER_NOTIFICATION.format(
                        title=cand.event_title,
                        humanized=keyboards.humanize_minutes(cand.offset_minutes),
                        close_at_fmt=cand.predictions_close_at.strftime("%d.%m %H:%M"),
                    ),
                    reply_markup=keyboards.main_menu(),
                )
                logger.info(
                    "scheduler.reminder.sent",
                    user_id=cand.user_id,
                    event_id=cand.event_id,
                    offset_minutes=cand.offset_minutes,
                )
            except TelegramAPIError as exc:
                logger.warning(
                    "scheduler.reminder.send_failed",
                    user_id=cand.user_id,
                    event_id=cand.event_id,
                    offset_minutes=cand.offset_minutes,
                    error=str(exc),
                )

        await session.commit()
