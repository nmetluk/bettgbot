"""Тесты `dispatch_reminders` (TASK-017) — мокаем сервис и репозиторий."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from src.bot.scheduler.jobs import dispatch_reminders
from src.shared.services import ReminderCandidate


def _make_session_maker(session: MagicMock) -> MagicMock:
    """Возвращает session_maker, который из `async with` отдаёт `session`."""

    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


def _make_candidate(**overrides: object) -> ReminderCandidate:
    defaults: dict[str, object] = {
        "tg_user_id": 100,
        "user_id": 1,
        "event_id": 10,
        "event_title": "Финал",
        "offset_minutes": 60,
        "predictions_close_at": datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ReminderCandidate(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def session_mock() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    return session


async def test_dispatch_reminders_sends_message_and_records_log(
    session_mock: MagicMock,
) -> None:
    cand = _make_candidate()
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    service_instance = MagicMock()
    service_instance.find_candidates = AsyncMock(return_value=[cand])

    repo_instance = MagicMock()
    repo_instance.record = AsyncMock(return_value=True)

    with (
        patch("src.bot.scheduler.jobs.ReminderService", return_value=service_instance),
        patch(
            "src.bot.scheduler.jobs.ReminderDispatchLogRepository",
            return_value=repo_instance,
        ),
    ):
        await dispatch_reminders(bot=bot, session_maker=_make_session_maker(session_mock))

    repo_instance.record.assert_awaited_once_with(
        user_id=cand.user_id,
        event_id=cand.event_id,
        offset_minutes=cand.offset_minutes,
    )
    bot.send_message.assert_awaited_once()
    sent_args, sent_kwargs = bot.send_message.call_args
    assert sent_args[0] == cand.tg_user_id
    assert "Финал" in sent_args[1]
    assert sent_kwargs["reply_markup"] is not None
    session_mock.commit.assert_awaited_once()


async def test_dispatch_reminders_skips_already_recorded(
    session_mock: MagicMock,
) -> None:
    cand = _make_candidate()
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    service_instance = MagicMock()
    service_instance.find_candidates = AsyncMock(return_value=[cand])

    repo_instance = MagicMock()
    repo_instance.record = AsyncMock(return_value=False)

    with (
        patch("src.bot.scheduler.jobs.ReminderService", return_value=service_instance),
        patch(
            "src.bot.scheduler.jobs.ReminderDispatchLogRepository",
            return_value=repo_instance,
        ),
    ):
        await dispatch_reminders(bot=bot, session_maker=_make_session_maker(session_mock))

    bot.send_message.assert_not_awaited()
    session_mock.commit.assert_awaited_once()


async def test_dispatch_reminders_logs_telegram_error_but_continues(
    session_mock: MagicMock,
) -> None:
    # Один кандидат падает на send, второй проходит — цикл не должен прерываться.
    cand_fail = _make_candidate(user_id=1, tg_user_id=100)
    cand_ok = _make_candidate(user_id=2, tg_user_id=200, event_id=20)
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock(
        side_effect=[TelegramAPIError(method=None, message="blocked"), None]
    )

    service_instance = MagicMock()
    service_instance.find_candidates = AsyncMock(return_value=[cand_fail, cand_ok])

    repo_instance = MagicMock()
    repo_instance.record = AsyncMock(return_value=True)

    with (
        patch("src.bot.scheduler.jobs.ReminderService", return_value=service_instance),
        patch(
            "src.bot.scheduler.jobs.ReminderDispatchLogRepository",
            return_value=repo_instance,
        ),
    ):
        await dispatch_reminders(bot=bot, session_maker=_make_session_maker(session_mock))

    assert bot.send_message.await_count == 2
    assert repo_instance.record.await_count == 2
    session_mock.commit.assert_awaited_once()
