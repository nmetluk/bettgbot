"""Реализации scheduler-job'ов."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.logging import get_logger
from src.shared.repositories import BroadcastRepository, ReminderDispatchLogRepository
from src.shared.services import EventService, ReminderService

from .. import keyboards, texts
from .._text_safety import safe_format

__all__ = [
    "archive_stale_events",
    "cleanup_old_dispatch_logs",
    "dispatch_broadcasts",
    "dispatch_reminders",
]


logger = get_logger(__name__)


async def dispatch_reminders(
    *, bot: Bot, session_maker: async_sessionmaker[AsyncSession], window_minutes: int = 10
) -> None:
    """Один тик scheduler'а: найти кандидатов и отправить им сообщения.

    Идемпотентность: `dispatch_log.record(...)` зовётся ДО `send_message`.
    Если запись не прошла (гонка) — пропускаем. Если send_message упал
    (TelegramAPIError, юзер заблокировал бота) — лог не откатываем:
    повторно слать уже бессмысленно, момент прошёл.

    Параметр `window_minutes` передаётся из scheduler (TASK-049), default
    обеспечивает совместимость при прямом вызове в тестах.
    """
    now = datetime.now(tz=UTC)
    async with session_maker() as session:
        service = ReminderService(session)
        candidates = await service.find_candidates(now=now, window_minutes=window_minutes)
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


async def dispatch_broadcasts(
    *, bot: Bot, session_maker: async_sessionmaker[AsyncSession], commit_batch_size: int = 50
) -> None:
    """Один тик scheduler'а: отправить одну queued-рассылку.

    Идемпотентность: `broadcast_delivery.record(...)` зовётся ДО `send_message`.
    Если запись не прошла (уже отправлено) — пропускаем.
    Если send_message упал (TelegramAPIError, юзер заблокировал бота) —
    инкрементим failed_count, но продолжаем (остальные получат сообщение).

    Пейсинг: ~0.05s между сообщениями (~20 msg/s), что ниже лимита Telegram (~30 msg/s).

    Безопасность: `parse_mode=None` (плоский текст), никакого HTML —
    исключает инъекцию при отправке пользовательского контента.

    Идемпотентность при рестарте: записи доставки фиксируются порциями
    (`commit_batch_size`, default 50). При крэше уже отправленные зафиксированы,
    повторная отправка исключается через UNIQUE constraint в delivery-log.
    """
    async with session_maker() as session:
        repo = BroadcastRepository(session)

        # Атомарно забираем одну queued-рассылку
        broadcast = await repo.claim_next_queued()
        if broadcast is None:
            return

        # Гард: пустой сегмент (должен был быть обработан при enqueue,
        # но на всякий случай)
        if broadcast.total_recipients == 0:
            await repo.mark_done(broadcast.id)
            await session.commit()
            logger.info(
                "scheduler.broadcast.empty",
                broadcast_id=broadcast.id,
            )
            return

        logger.info(
            "scheduler.broadcast.started",
            broadcast_id=broadcast.id,
            segment=broadcast.segment,
            total_recipients=broadcast.total_recipients,
        )

        # Коммитим переход queued→sending сразу, чтобы освободить лок
        # и зафиксировать факт старта (рестарт не начнёт параллельно)
        await session.commit()

        # Получаем список получателей (закеширован в репо, отдельный select)
        recipients = await repo.recipients_for(
            segment=broadcast.segment, category_id=broadcast.category_id
        )

        # Для порционного коммита
        batch_counter = 0

        for user_id in recipients:
            # Идемпотентность: записываем факт доставки ДО отправки
            recorded = await repo.record_delivery(broadcast.id, user_id)
            if not recorded:
                # Уже отправлено (возможно при предыдущем тике после рестарта)
                continue

            # Получаем tg_user_id для отправки
            # (нужен отдельный запрос, так как recipients_for возвращает только user_id)
            from src.shared.repositories import UserRepository

            user_repo = UserRepository(session)
            user = await user_repo.get_by_id(user_id)
            if user is None or user.is_blocked:
                # Пользователь удалён или заблокирован после подсчёта recipients
                await repo.increment_failed(broadcast.id)
                batch_counter += 1
                continue

            try:
                await bot.send_message(user.tg_user_id, broadcast.message_text)
                await repo.increment_sent(broadcast.id)
                logger.debug(
                    "scheduler.broadcast.sent",
                    broadcast_id=broadcast.id,
                    user_id=user_id,
                )
            except TelegramAPIError as exc:
                await repo.increment_failed(broadcast.id)
                logger.warning(
                    "scheduler.broadcast.send_failed",
                    broadcast_id=broadcast.id,
                    user_id=user_id,
                    error=str(exc),
                )

            batch_counter += 1

            # Пейсинг: ~20 msg/s (0.05s = 50ms между сообщениями)
            await asyncio.sleep(0.05)

            # Порционный коммит для идемпотентности при рестарте
            if batch_counter >= commit_batch_size:
                await session.commit()
                batch_counter = 0

        # Финальный коммит для оставшихся записей
        await repo.mark_done(broadcast.id)
        await session.commit()

        logger.info(
            "scheduler.broadcast.done",
            broadcast_id=broadcast.id,
            sent_count=broadcast.sent_count,
            failed_count=broadcast.failed_count,
        )
