"""Unit-тесты `send_daily_admin_digest` (TASK-097 + TASK-098) с замоканным Bot.

Покрывает early-return, нормальный путь и обогащение (дельты, DAU и т.д.).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from freezegun import freeze_time
from src.bot.scheduler.jobs import send_daily_admin_digest


def _make_session_maker(session: MagicMock) -> MagicMock:
    """Возвращает session_maker, который отдаёт session в async with."""

    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


@pytest.fixture
def session_mock() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    return session


def _mk_settings(chat_ids: list[int]) -> MagicMock:
    s = MagicMock()
    s.admin_telegram_chat_ids = chat_ids
    return s


async def test_send_daily_admin_digest_skips_on_empty_recipients_no_crash(
    session_mock: MagicMock,
) -> None:
    """Пустой ADMIN_TELEGRAM_CHAT_IDS → не шлёт, не падает, БД не трогаем."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with patch("src.shared.config.get_settings", return_value=_mk_settings([])):
        await send_daily_admin_digest(bot=bot, session_maker=_make_session_maker(session_mock))

    bot.send_message.assert_not_called()
    # session_maker не должен вызываться (early return до async with)
    # (в данном вызове maker не был использован)


@freeze_time("2026-06-01 12:00:00+00:00")
async def test_send_daily_admin_digest_sends_to_all_chats_with_correct_24h_numbers(
    session_mock: MagicMock,
) -> None:
    """Заполненный список → send_message на каждый chat_id; обогащённые данные (в т.ч. дельты) верны."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    settings = _mk_settings([111, 222])

    digest = MagicMock()
    digest.total_users = 1234
    digest.new_24h = 42
    digest.new_24h_delta = 5
    digest.preds_24h = 87
    digest.preds_24h_delta = -3
    digest.dau_24h = 100
    digest.active_events_now = 5
    digest.top_events_24h = [("Event A", 10), ("Event B", 7)]
    digest.closed_correct = 2
    digest.closed_total = 5
    digest.closed_accuracy_pct = 40.0
    digest.converted_new = 10
    digest.total_new_for_conv = 20
    digest.conversion_pct = 50.0

    expected_now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    with (
        patch("src.shared.config.get_settings", return_value=settings),
        patch("src.bot.scheduler.jobs.StatsService") as stats_cls,
    ):
        stats_instance = MagicMock()
        stats_instance.daily_admin_digest = AsyncMock(return_value=digest)
        stats_cls.return_value = stats_instance

        await send_daily_admin_digest(bot=bot, session_maker=_make_session_maker(session_mock))

    # Отправка ровно в 2 чата
    assert bot.send_message.await_count == 2
    calls = [c for c in bot.send_message.call_args_list]
    assert calls[0][0][0] == 111
    assert calls[1][0][0] == 222

    # Текст содержит обогащённые данные и форматирование дельт/нулей
    text0 = calls[0][0][1]
    assert "2026-06-01" in text0
    assert "1234" in text0
    assert "42" in text0
    assert "▲ +5" in text0
    assert "87" in text0
    assert "▼ -3" in text0
    assert "100" in text0  # dau
    assert "5" in text0  # active
    assert "Event A: 10" in text0
    assert "2/5 (40.0%)" in text0
    assert "10/20 (50.0%)" in text0

    # Сервис вызван с корректным reference_now (для детерминизма окон, TASK-102)
    stats_instance.daily_admin_digest.assert_awaited_once_with(reference_now=expected_now)
