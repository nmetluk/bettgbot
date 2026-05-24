"""Smoke-тест сборки scheduler'а (TASK-017)."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.bot.scheduler import build_scheduler


def test_build_scheduler_registers_dispatch_reminders_job() -> None:
    bot = MagicMock(spec=Bot)
    session_maker = MagicMock()

    scheduler = build_scheduler(bot=bot, session_maker=session_maker)

    assert isinstance(scheduler, AsyncIOScheduler)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "dispatch_reminders"
    assert isinstance(job.trigger, IntervalTrigger)
    # IntervalTrigger хранит interval как datetime.timedelta(minutes=5).
    assert job.trigger.interval.total_seconds() == 5 * 60
    assert job.misfire_grace_time == 60
