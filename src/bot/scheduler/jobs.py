"""Реализации scheduler-job'ов."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.shared.logging import get_logger
from src.shared.models import Event
from src.shared.repositories import (
    BackupRunRepository,
    BroadcastRepository,
    ReminderDispatchLogRepository,
)
from src.shared.services import EventService, ReminderService, StatsService
from src.shared.time import utcnow

from .. import keyboards, texts
from .._csv import generate_correct_users_csv
from .._text_safety import safe_format

__all__ = [
    "archive_stale_events",
    "cleanup_old_dispatch_logs",
    "dispatch_broadcasts",
    "dispatch_event_result_notifications",
    "dispatch_reminders",
    "replicate_latest_backup",
    "send_backup_health_heartbeat",
    "send_daily_admin_digest",
]


logger = get_logger(__name__)


async def dispatch_reminders(
    *,
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    window_minutes: int = 10,
    commit_batch_size: int = 50,
) -> None:
    """Один тик scheduler'а: найти кандидатов и отправить им сообщения.

    Идемпотентность: `dispatch_log.record(...)` зовётся ДО `send_message`.
    Если запись не прошла (гонка) — пропускаем. Если send_message упал
    (TelegramAPIError, юзер заблокировал бота) — лог не откатываем:
    повторно слать уже бессмысленно, момент прошёл.

    Параметр `window_minutes` передаётся из scheduler (TASK-049), default
    обеспечивает совместимость при прямом вызове в тестах.

    Crash-safety (TASK-086): записи в reminder_dispatch_log фиксируются
    порциями (`commit_batch_size`). При рестарте бота в середине батча
    уже обработанные кандидаты не отправляются повторно (UNIQUE + ON CONFLICT).
    Кандидаты материализуются в список до цикла отправок (иначе commit
    может повлиять на ленивую выборку).
    """
    now = utcnow()
    async with session_maker() as session:
        service = ReminderService(session)
        candidates = await service.find_candidates(now=now, window_minutes=window_minutes)
        # Важно: материализуем до цикла. После первого commit() ленивая
        # выборка из find_candidates может быть в неконсистентном состоянии.
        candidates = list(candidates)

        dispatch_log = ReminderDispatchLogRepository(session)
        batch_counter = 0

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

            batch_counter += 1
            if batch_counter >= commit_batch_size:
                await session.commit()
                batch_counter = 0

        # Финальный коммит для остатка батча (< commit_batch_size)
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
    cutoff = utcnow() - timedelta(days=retention_days)
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


# =============================================================================
# АДМИН-СТАТИСТИКА ЧЕРЕЗ БОТА (TASK-097)
# =============================================================================


async def send_daily_admin_digest(
    *,
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Ежедневный дайджест админам в 16:00 Europe/Moscow.

    Считает: total users (count_for_admin), new за 24ч, прогнозы за 24ч.
    Пустой ADMIN_TELEGRAM_CHAT_IDS → warning + return (БД не трогаем).
    """
    from src.shared.config import get_settings

    settings = get_settings()
    chat_ids = settings.admin_telegram_chat_ids
    if not chat_ids:
        logger.warning("scheduler.admin_digest.skipped_empty_recipients")
        return

    async with session_maker() as session:
        from src.shared.repositories import PredictionRepository, UserRepository

        user_repo = UserRepository(session)
        pred_repo = PredictionRepository(session)

        total = await user_repo.count_for_admin(query=None)
        cutoff = utcnow() - timedelta(hours=24)
        new_24h = await user_repo.count_new_since(cutoff)
        preds_24h = await pred_repo.count_24h()

        date_str = utcnow().strftime("%Y-%m-%d")

        text = safe_format(
            texts.ADMIN_DAILY_DIGEST,
            date=date_str,
            total=total,
            new_24h=new_24h,
            preds_24h=preds_24h,
        )

        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id, text)
                logger.info(
                    "scheduler.admin_digest.sent",
                    chat_id=chat_id,
                    total=total,
                    new_24h=new_24h,
                )
            except TelegramAPIError as exc:
                logger.warning(
                    "scheduler.admin_digest.send_failed",
                    chat_id=chat_id,
                    error=str(exc),
                )


async def dispatch_event_result_notifications(
    *,
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    """Пост-итоговые сводки админам после фиксации результата события.

    Ищет события с result_outcome_id IS NOT NULL AND result_notified_at IS NULL.
    Использует FOR UPDATE SKIP LOCKED (как claim у broadcasts).
    Для каждого: считает summary через StatsService, шлёт текст + CSV (если есть)
    во все ADMIN_TELEGRAM_CHAT_IDS, затем result_notified_at=now() и commit (per-event).

    Пустой список получателей → warning, события НЕ трогаем (не помечаем notified).
    Ошибка отправки в один чат → warning, продолжаем; событие всё равно помечаем
    (повторная рассылка хуже потери одного чата).
    """
    from src.shared.config import get_settings

    settings = get_settings()
    chat_ids = settings.admin_telegram_chat_ids
    if not chat_ids:
        logger.warning("scheduler.event_result_notifications.skipped_empty_recipients")
        return

    async with session_maker() as session:
        # Забираем кандидатов под лок (skip locked — не блокируемся на уже обрабатываемых)
        stmt = (
            select(Event)
            .where(
                Event.result_outcome_id.isnot(None),
                Event.result_notified_at.is_(None),
            )
            .order_by(Event.id)
            .with_for_update(skip_locked=True)
            .limit(20)  # небольшой батч на тик
        )
        events = (await session.execute(stmt)).scalars().all()

        for event in events:
            summary = await StatsService(session).event_result_summary(event.id)

            # Форматируем текст (используем константы из texts, не хардкод)
            header = safe_format(
                texts.ADMIN_EVENT_RESULT_HEADER,
                event_id=event.id,
                title=event.title,
            )

            # Распределение
            lines: list[str] = []
            for _oid, label, cnt, is_winner in summary.outcome_distribution:
                emoji = "✅" if is_winner else "•"
                pct = (
                    round((cnt / summary.total_predictions * 100), 1)
                    if summary.total_predictions
                    else 0
                )
                line = safe_format(
                    texts.ADMIN_EVENT_RESULT_OUTCOME_LINE,
                    emoji=emoji,
                    label=label,
                    count=cnt,
                    pct=pct,
                )
                lines.append(line)
            dist_block = "\n".join(lines) if lines else "—"

            correct_block = safe_format(
                texts.ADMIN_EVENT_RESULT_CORRECT,
                correct=summary.correct_count,
            )

            csv_note = ""
            csv_file: BufferedInputFile | None = None
            if summary.correct_count > 0:
                csv_file = generate_correct_users_csv(summary.correct_users, event.id)
                if csv_file:
                    csv_note = texts.ADMIN_EVENT_RESULT_CSV_NOTE

            text = f"{header}\n\nВсего прогнозов: <b>{summary.total_predictions}</b>\n{dist_block}{correct_block}{csv_note}"

            # Отправляем во все чаты (даже если один упадёт — помечаем notified)
            for chat_id in chat_ids:
                try:
                    await bot.send_message(chat_id, text, disable_web_page_preview=True)
                    if csv_file:
                        await bot.send_document(chat_id, csv_file)
                except TelegramAPIError as exc:
                    logger.warning(
                        "scheduler.event_result.send_failed",
                        event_id=event.id,
                        chat_id=chat_id,
                        error=str(exc),
                    )

            # Помечаем как разосланное (даже при частичных ошибках отправки)
            event.result_notified_at = utcnow()
            await session.flush()
            await session.commit()

            logger.info(
                "scheduler.event_result.notified",
                event_id=event.id,
                total=summary.total_predictions,
                correct=summary.correct_count,
            )


# =============================================================================
# TASK-099: Backup health heartbeat (внутренний мониторинг бэкапов)
# =============================================================================


async def _check_postgres_visible(session: AsyncSession, timeout_seconds: float = 5.0) -> bool:
    """Проверка доступности Postgres из инстанса бота (с таймаутом)."""
    from sqlalchemy import text

    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout_seconds)
        return True
    except Exception:
        return False


async def _check_redis_visible() -> bool:
    """Проверка доступности Redis (если сконфигурирован). Неблокирующая, с таймаутом (per amendment).

    redis_url declared as required in Settings (no getattr guess). Uses to_thread + wait_for to not block loop.
    """
    from src.shared.config import get_settings

    settings = get_settings()
    # redis_url is a top-level required field in Settings (RedisDsn), not guessed via hasattr.
    redis_url = settings.redis_url
    if not redis_url:
        return True

    def _sync_ping() -> bool:
        import redis

        r = redis.from_url(str(redis_url), socket_connect_timeout=3)  # type: ignore[no-untyped-call]
        r.ping()
        return True

    try:
        return await asyncio.wait_for(asyncio.to_thread(_sync_ping), timeout=5.0)
    except Exception:
        return False


async def send_backup_health_heartbeat(
    *, bot: Bot, session_maker: async_sessionmaker[AsyncSession]
) -> None:
    """Ежечасный heartbeat о здоровье бэкапов (TASK-099).

    Читает последнюю запись из backup_run + проверяет видимость БД/Redis.
    Отправляет OK или ALERT во все ADMIN_TELEGRAM_CHAT_IDS.
    """
    from src.shared.config import get_settings

    settings = get_settings()
    if not settings.backup.heartbeat_enabled:
        return

    chat_ids = settings.admin_telegram_chat_ids
    if not chat_ids:
        logger.warning("scheduler.backup_heartbeat.skipped_empty_recipients")
        return

    max_age = timedelta(hours=settings.backup.max_age_hours)
    rep_lag = timedelta(hours=settings.backup.replication_max_lag_hours)

    async with session_maker() as session:
        repo = BackupRunRepository(session)
        last_success = await repo.get_last_success()
        latest = await repo.get_latest()

        db_ok = await _check_postgres_visible(session)
        redis_ok = await _check_redis_visible()

        now = utcnow()

        # Формируем статус. Всегда отправляем отчёт (даже "no recent backups" — per amendment).
        if not last_success:
            text = safe_format(
                texts.OPERATIONAL_HEARTBEAT_NO_RECENT,
                db_ok="OK" if db_ok else "DOWN",
                redis_ok="OK" if redis_ok else "DOWN",
            )
        else:
            age = now - last_success.finished_at if last_success.finished_at else timedelta.max
            age_str = (
                f"{int(age.total_seconds() // 3600)}h {int((age.total_seconds() % 3600) // 60)}m"
            )

            rep_age = (
                now - last_success.replicated_at if last_success.replicated_at else timedelta.max
            )
            rep_lag_str = (
                f"{int(rep_age.total_seconds() // 3600)}h"
                if rep_age != timedelta.max
                else "никогда"
            )

            if latest and latest.status == "failed":
                reason = "Последний бэкап завершился с ошибкой"
                text = safe_format(
                    texts.OPERATIONAL_HEARTBEAT_ALERT,
                    reason=reason,
                    last=age_str,
                    db_ok="OK" if db_ok else "DOWN",
                    redis_ok="OK" if redis_ok else "DOWN",
                )
            elif age > max_age:
                reason = f"Последний успешный бэкап старше {settings.backup.max_age_hours}ч"
                text = safe_format(
                    texts.OPERATIONAL_HEARTBEAT_ALERT,
                    reason=reason,
                    last=age_str,
                    db_ok="OK" if db_ok else "DOWN",
                    redis_ok="OK" if redis_ok else "DOWN",
                )
            elif last_success.replicated_at is None or rep_age > rep_lag:
                reason = f"Репликация не выполнена (lag {rep_lag_str} > {settings.backup.replication_max_lag_hours}ч)"
                text = safe_format(
                    texts.OPERATIONAL_HEARTBEAT_ALERT,
                    reason=reason,
                    last=age_str,
                    db_ok="OK" if db_ok else "DOWN",
                    redis_ok="OK" if redis_ok else "DOWN",
                )
            else:
                size_str = (
                    f"{last_success.size_bytes // (1024 * 1024)}M"
                    if last_success.size_bytes
                    else "N/A"
                )
                replication = "реплицирован" if last_success.replicated_at else "не реплицирован"
                text = safe_format(
                    texts.OPERATIONAL_HEARTBEAT_OK,
                    last_success_age=age_str,
                    size=size_str,
                    db_ok="OK" if db_ok else "DOWN",
                    redis_ok="OK" if redis_ok else "DOWN",
                    replication=replication,
                )

        # Рассылка (ошибка в одном чате не останавливает остальные)
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id, text)
                logger.info(
                    "scheduler.backup_heartbeat.sent",
                    chat_id=chat_id,
                    status="ok" if "✅" in text else "alert",
                )
            except TelegramAPIError as exc:
                logger.warning(
                    "scheduler.backup_heartbeat.send_failed",
                    chat_id=chat_id,
                    error=str(exc),
                )


# =============================================================================
# TASK-100: Backup replication (pull latest unreplicated dump from Admin to Bot via SSH/rsync)
# =============================================================================


async def _run_rsync_pull(
    *,
    user: str,
    host: str,
    key_path: Path,
    remote_path: str,
    local_path: Path,
    timeout_s: float = 300.0,
) -> None:
    """Выполнить rsync pull дампа по SSH. Идемпотентно, с таймаутом. Ключ не логируется."""
    cmd = [
        "rsync",
        "-az",
        "-e",
        f"ssh -i {key_path} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null",
        f"{user}@{host}:{remote_path}",
        str(local_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        if proc.returncode != 0:
            # Не логируем ключ; stderr может содержать детали, но обрезаем чувствительное
            err = stderr.decode(errors="ignore") if stderr else ""
            raise RuntimeError(f"rsync failed (code {proc.returncode}): {err[:500]}")
    except TimeoutError:
        raise RuntimeError(f"rsync timed out after {timeout_s}s") from None


async def replicate_latest_backup(*, session_maker: async_sessionmaker[AsyncSession]) -> None:
    """Периодический pull репликации последнего непрореплицированного дампа (TASK-100).

    Берёт последний success с replicated_at IS NULL, rsync-pull по SSH, при успехе mark_replicated.
    Ошибки логируются warning (heartbeat покажет статус).
    """
    from src.shared.config import get_settings

    settings = get_settings()
    if not settings.backup.replication_enabled:
        return

    # Определяем host: explicit или fallback (ADMIN_DOMAIN может быть в env, но для простоты используем source_host)
    host = settings.backup.source_host
    if not host:
        # Fallback: попробовать ADMIN_DOMAIN из env (как в compose)
        import os

        host = os.environ.get("ADMIN_DOMAIN")
    if not host:
        logger.warning("scheduler.backup_replication.skipped_no_source_host")
        return

    user = settings.backup.source_ssh_user
    key_path = settings.backup.ssh_key_path
    source_dir = settings.backup.source_dir.rstrip("/")
    local_dir = settings.backup.local_dir

    local_dir.mkdir(parents=True, exist_ok=True)

    async with session_maker() as session:
        repo = BackupRunRepository(session)
        last_unrep = await repo.get_last_unreplicated_success()
        if not last_unrep or not last_unrep.filename:
            return  # ничего реплицировать, или heartbeat покажет

        filename = last_unrep.filename
        remote = f"{source_dir}/{filename}"
        local_target = local_dir / filename

        try:
            await _run_rsync_pull(
                user=user,
                host=host,
                key_path=key_path,
                remote_path=remote,
                local_path=local_target,
            )
            await repo.mark_replicated(last_unrep.id, utcnow())
            await session.commit()
            logger.info(
                "scheduler.backup_replication.success",
                filename=filename,
                host=host,
            )
        except Exception as exc:
            logger.warning(
                "scheduler.backup_replication.failed",
                filename=filename,
                host=host,
                error=str(exc),
            )
