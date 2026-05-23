"""Routers бота. Порядок регистрации — порядок, в котором aiogram проверяет handler'ы."""

from __future__ import annotations

from aiogram import Router

from .events import router as events_router
from .help import router as help_router
from .my import router as my_router
from .prediction import router as prediction_router
from .reminders import router as reminders_router
from .start import router as start_router

__all__ = ["all_routers"]


# `start` идёт первым: незарегистрированный пользователь должен попасть в /start
# раньше, чем в любую другую команду.
all_routers: list[Router] = [
    start_router,
    events_router,
    prediction_router,
    my_router,
    reminders_router,
    help_router,
]
