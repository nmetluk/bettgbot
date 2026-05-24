"""Тесты `cmd_help` — статическая справка (TASK-016)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message, ReplyKeyboardMarkup
from src.bot import texts
from src.bot.routers.help import cmd_help


def _mock_message() -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.answer = AsyncMock()
    return msg


async def test_cmd_help_unauthenticated_sends_need_start() -> None:
    msg = _mock_message()
    await cmd_help(msg, user=None, session=MagicMock())
    args, _ = msg.answer.call_args
    assert args[0] == texts.NEED_START


async def test_cmd_help_blocked_sends_access_denied() -> None:
    msg = _mock_message()
    user = MagicMock(is_blocked=True)
    await cmd_help(msg, user=user, session=MagicMock())
    args, _ = msg.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_cmd_help_active_user_sends_help_text_with_main_menu() -> None:
    msg = _mock_message()
    user = MagicMock(is_blocked=False)
    await cmd_help(msg, user=user, session=MagicMock())
    msg.answer.assert_awaited_once()
    args, kwargs = msg.answer.call_args
    assert args[0] == texts.HELP
    kb = kwargs["reply_markup"]
    assert isinstance(kb, ReplyKeyboardMarkup)
    # 5 кнопок главного меню в 3 ряда (2 + 2 + 1).
    assert len(kb.keyboard) == 3
