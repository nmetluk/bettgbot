"""Тесты `cmd_start` — ветки регистрации, возврата, блокировки."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from src.bot import texts
from src.bot.routers.start import cmd_start


def _mock_message() -> MagicMock:
    message = MagicMock()
    message.answer = AsyncMock()
    message.from_user = MagicMock(id=12345, username="alice", first_name="Alice")
    return message


def _mock_state() -> MagicMock:
    state = MagicMock()
    state.clear = AsyncMock()
    return state


async def test_cmd_start_new_user_sends_welcome_new_with_contact_keyboard() -> None:
    message = _mock_message()
    state = _mock_state()
    await cmd_start(message, user=None, state=state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.call_args
    assert args[0] == texts.WELCOME_NEW
    kb = kwargs["reply_markup"]
    assert isinstance(kb, ReplyKeyboardMarkup)
    # одна кнопка с request_contact
    assert kb.keyboard[0][0].request_contact is True


async def test_cmd_start_returning_user_sends_main_menu() -> None:
    message = _mock_message()
    state = _mock_state()
    user = MagicMock(id=7, is_blocked=False)
    await cmd_start(message, user=user, state=state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.call_args
    assert args[0] == texts.WELCOME_RETURNING
    kb = kwargs["reply_markup"]
    assert isinstance(kb, ReplyKeyboardMarkup)
    # 5 кнопок: 2 + 2 + 1
    assert len(kb.keyboard) == 3


async def test_cmd_start_blocked_user_sends_access_denied() -> None:
    message = _mock_message()
    state = _mock_state()
    user = MagicMock(id=8, is_blocked=True)
    await cmd_start(message, user=user, state=state)

    message.answer.assert_awaited_once()
    args, kwargs = message.answer.call_args
    assert args[0] == texts.ACCESS_DENIED
    assert isinstance(kwargs["reply_markup"], ReplyKeyboardRemove)


async def test_cmd_start_clears_fsm() -> None:
    message = _mock_message()
    state = _mock_state()
    await cmd_start(message, user=None, state=state)
    state.clear.assert_awaited_once()
