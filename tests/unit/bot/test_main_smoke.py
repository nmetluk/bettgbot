"""Smoke-тест сборки dispatcher'а: `python -m src.bot.main` не должен упасть на bootstrap'е."""

from __future__ import annotations

import pytest
from aiogram import Bot, Dispatcher


def test_dispatcher_constructs(monkeypatch: pytest.MonkeyPatch) -> None:
    # aiogram валидирует формат токена `<digits>:<string>`; локальный `.env`
    # может содержать любой stub — перетираем явно для теста.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111111:stub-token")

    from src.shared.config import get_settings

    get_settings.cache_clear()

    from src.bot.main import build_dispatcher

    bot, dp = build_dispatcher()
    assert isinstance(bot, Bot)
    assert isinstance(dp, Dispatcher)

    # 6 routers зарегистрированы (start, events, prediction, my, reminders, help).
    assert len(dp.sub_routers) == 6
    router_names = {r.name for r in dp.sub_routers}
    assert router_names == {
        "start",
        "events",
        "prediction",
        "my",
        "reminders",
        "help",
    }
