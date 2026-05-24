"""Smoke-тест сборки scheduler'а (TASK-017, TASK-018)."""

from __future__ import annotations

from unittest.mock import MagicMock

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
    assert job.misfire_grace_time == 60


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
