"""Фабрика `AsyncIOScheduler` с зарегистрированными job'ами."""

from __future__ import annotations

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .jobs import dispatch_reminders

__all__ = ["build_scheduler"]


def build_scheduler(
    *, bot: Bot, session_maker: async_sessionmaker[AsyncSession]
) -> AsyncIOScheduler:
    """Собирает scheduler с reminder-job каждые 5 минут.

    UTC + `misfire_grace_time=60`: если scheduler пропустит тик (нагрузка,
    рестарт бота на минуту-две), он догонит при следующем интервале.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        dispatch_reminders,
        trigger=IntervalTrigger(minutes=5),
        kwargs={"bot": bot, "session_maker": session_maker},
        id="dispatch_reminders",
        replace_existing=True,
        misfire_grace_time=60,
    )
    return scheduler
