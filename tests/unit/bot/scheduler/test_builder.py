"""Smoke-тест сборки scheduler'а (TASK-017, TASK-018)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.bot.scheduler import build_scheduler


def test_build_scheduler_registers_dispatch_reminders_job() -> None:
    bot = MagicMock(spec=Bot)
    session_maker = MagicMock()

    scheduler = build_scheduler(bot=bot, session_maker=session_maker)

    assert isinstance(scheduler, AsyncIOScheduler)
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert "dispatch_reminders" in jobs
    job = jobs["dispatch_reminders"]
    assert isinstance(job.trigger, IntervalTrigger)
    # IntervalTrigger хранит interval как datetime.timedelta(minutes=5).
    assert job.trigger.interval.total_seconds() == 5 * 60
    # TASK-049: misfire_grace_time повышен до 3600 для catchup при restart.
    assert job.misfire_grace_time == 3600


def test_build_scheduler_registers_archive_stale_events_job() -> None:
    scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}

    assert "archive_stale_events" in jobs
    job = jobs["archive_stale_events"]
    assert isinstance(job.trigger, CronTrigger)
    # CronTrigger.fields содержит описание полей расписания.
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "3"
    assert fields["minute"] == "0"
    assert job.misfire_grace_time == 300


# =============================================================================
# TASK-097: регистрация новых админ-джобов (по amendment-2)
# =============================================================================


def test_build_scheduler_registers_send_daily_admin_digest_job() -> None:
    """Дайджест: id, CronTrigger с timezone=Europe/Moscow, coalesce/max=1."""
    scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}

    assert "send_daily_admin_digest" in jobs
    job = jobs["send_daily_admin_digest"]
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "16"
    assert fields["minute"] == "0"
    # timezone задаётся per-job (не дефолт UTC scheduler'а)
    assert str(job.trigger.timezone) == "Europe/Moscow"
    assert job.misfire_grace_time == 3600
    assert job.coalesce is True
    assert job.max_instances == 1


def test_build_scheduler_registers_dispatch_event_result_notifications_job() -> None:
    """Нотификации: id, IntervalTrigger(minutes=1), coalesce/max=1."""
    scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}

    assert "dispatch_event_result_notifications" in jobs
    job = jobs["dispatch_event_result_notifications"]
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 60
    assert job.misfire_grace_time == 300
    assert job.coalesce is True
    assert job.max_instances == 1


def _mk_settings_backup(enabled: bool) -> MagicMock:
    s = MagicMock()
    s.backup.heartbeat_enabled = enabled
    s.backup.max_age_hours = 2
    s.admin_telegram_chat_ids = [123]
    return s


def _mk_settings_replication(enabled: bool) -> MagicMock:
    s = MagicMock()
    s.backup.replication_enabled = enabled
    s.backup.source_host = "10.0.0.1"
    s.backup.source_ssh_user = "root"
    s.backup.ssh_key_path = "/key"
    s.backup.source_dir = "/backups"
    s.backup.local_dir = "/backups"
    s.backup.replication_max_lag_hours = 3
    return s


def test_build_scheduler_backup_heartbeat_not_registered_when_disabled() -> None:
    """BACKUP_HEARTBEAT_ENABLED=false → джоб НЕ зарегистрирован."""
    with patch("src.shared.config.get_settings", return_value=_mk_settings_backup(False)):
        scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert "send_backup_health_heartbeat" not in jobs


def test_build_scheduler_backup_heartbeat_registered_when_enabled() -> None:
    """BACKUP_HEARTBEAT_ENABLED=true → зарегистрирован с id и CronTrigger(minute=7), coalesce/max=1."""
    with patch("src.shared.config.get_settings", return_value=_mk_settings_backup(True)):
        scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}

    assert "send_backup_health_heartbeat" in jobs
    job = jobs["send_backup_health_heartbeat"]
    assert isinstance(job.trigger, CronTrigger)
    # minute=7 (ежечасно в :07, без tz — как в билдере)
    trigger_repr = repr(job.trigger)
    assert "minute" in trigger_repr and "7" in trigger_repr
    assert job.coalesce is True
    assert job.max_instances == 1
    assert job.misfire_grace_time == 600


def test_build_scheduler_backup_replication_not_registered_when_disabled() -> None:
    """BACKUP_REPLICATION_ENABLED=false → джоб репликации НЕ зарегистрирован."""
    with patch("src.shared.config.get_settings", return_value=_mk_settings_replication(False)):
        scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert "replicate_latest_backup" not in jobs


def test_build_scheduler_backup_replication_registered_when_enabled() -> None:
    """BACKUP_REPLICATION_ENABLED=true → зарегистрирован с id и IntervalTrigger(minutes=15)."""
    with patch("src.shared.config.get_settings", return_value=_mk_settings_replication(True)):
        scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
    jobs = {j.id: j for j in scheduler.get_jobs()}

    assert "replicate_latest_backup" in jobs
    job = jobs["replicate_latest_backup"]
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 15 * 60
    assert job.coalesce is True
    assert job.max_instances == 1
    assert job.misfire_grace_time == 600
