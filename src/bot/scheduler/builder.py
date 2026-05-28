"""Фабрика `AsyncIOScheduler` с зарегистрированными job'ами."""

from __future__ import annotations

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .jobs import archive_stale_events, cleanup_old_dispatch_logs, dispatch_reminders

__all__ = ["build_scheduler"]


def build_scheduler(
    *, bot: Bot, session_maker: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    """Собирает scheduler с job'ами проекта.

    - `dispatch_reminders`: каждые 5 минут UTC, `misfire_grace_time=3600`
      (TASK-049 — extended для catchup при restart/misfire), `coalesce=True`,
      `max_instances=1`. Окно поиска кандидатов — `reminder_window_minutes` из
      settings (default 10 минут = tick + запас).
    - `archive_stale_events`: ежедневно в 03:00 UTC, `misfire_grace_time=300`
      (cron-job менее чувствителен ко времени).
    - `cleanup_old_dispatch_logs`: ежедневно в 03:30 UTC, `misfire_grace_time=300`
      (TASK-048 — retention для reminder_dispatch_log).
    """
    from src.shared.config import get_settings

    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        dispatch_reminders,
        trigger=IntervalTrigger(minutes=5),
        kwargs={"bot": bot, "session_maker": session_maker, "window_minutes": settings.reminder_window_minutes},
        id="dispatch_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        archive_stale_events,
        trigger=CronTrigger(hour=3, minute=0),
        kwargs={"session_maker": session_maker},
        id="archive_stale_events",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        cleanup_old_dispatch_logs,
        trigger=CronTrigger(hour=3, minute=30),
        kwargs={"session_maker": session_maker, "retention_days": settings.reminder_log_retention_days},
        id="cleanup_old_dispatch_logs",
        replace_existing=True,
        misfire_grace_time=300,
    )
    return scheduler
