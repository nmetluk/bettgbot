"""Реализации scheduler-job'ов."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.logging import get_logger
from src.shared.repositories import ReminderDispatchLogRepository
from src.shared.services import EventService, ReminderService

from .. import keyboards, texts
from .._text_safety import safe_format

__all__ = ["archive_stale_events", "cleanup_old_dispatch_logs", "dispatch_reminders"]


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
                    safe_format(
                        texts.REMINDER_NOTIFICATION,
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


async def archive_stale_events(*, session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Ежедневный job: архивирует события старше 7 дней без зафиксированного итога.

    Без TG-side-effects — только update в БД. Логирует количество архивированных
    событий даже при нуле (sysadmin'у нужен sanity check «job отработал»).
    """
    async with session_maker() as session:
        service = EventService(session)
        count = await service.archive_stale_events()
        logger.info("scheduler.archive_stale.done", archived_count=count)


async def cleanup_old_dispatch_logs(
    *, session_maker: async_sessionmaker[AsyncSession], retention_days: int
) -> None:
    """Ежедневный job: удаляет старые записи из reminder_dispatch_log (TASK-048).

    Без TG-side-effects — только DELETE в БД. Логирует количество удалённых строк
    даже при нуле (sysadmin'у нужен sanity check «job отработал»).
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    async with session_maker() as session:
        dispatch_log = ReminderDispatchLogRepository(session)
        count = await dispatch_log.delete_older_than(cutoff)
        await session.commit()
        logger.info(
            "scheduler.cleanup_dispatch_logs.done",
            deleted_count=count,
            retention_days=retention_days,
        )
