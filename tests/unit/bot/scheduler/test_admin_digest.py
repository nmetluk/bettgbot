"""Unit-тесты `send_daily_admin_digest` (TASK-097) с замоканным Bot.

Покрывает early-return на пустом списке получателей и нормальный путь
(отправка во все chat_id, корректные цифры 24h-окна в тексте).
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
    """Заполненный список → send_message на каждый chat_id; цифры 24h-окна верны."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    settings = _mk_settings([111, 222])

    user_repo = MagicMock()
    user_repo.count_for_admin = AsyncMock(return_value=1234)
    user_repo.count_new_since = AsyncMock(return_value=42)

    pred_repo = MagicMock()
    pred_repo.count_24h = AsyncMock(return_value=87)

    expected_cutoff = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)

    with (
        patch("src.shared.config.get_settings", return_value=settings),
        patch("src.shared.repositories.UserRepository", return_value=user_repo),
        patch("src.shared.repositories.PredictionRepository", return_value=pred_repo),
    ):
        await send_daily_admin_digest(bot=bot, session_maker=_make_session_maker(session_mock))

    # Отправка ровно в 2 чата
    assert bot.send_message.await_count == 2
    calls = [c for c in bot.send_message.call_args_list]
    assert calls[0][0][0] == 111
    assert calls[1][0][0] == 222

    # Текст содержит дату и все цифры (из замороженного now и моков)
    text0 = calls[0][0][1]
    assert "2026-06-01" in text0
    assert "1234" in text0  # total
    assert "42" in text0  # new_24h
    assert "87" in text0  # preds_24h

    # Репозитории вызваны с корректными аргументами (24h окно)
    user_repo.count_new_since.assert_awaited_once_with(expected_cutoff)
    pred_repo.count_24h.assert_awaited_once_with()
