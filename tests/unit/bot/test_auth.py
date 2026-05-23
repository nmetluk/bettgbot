"""Тесты декоратора `@require_active_user`."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message
from src.bot import texts
from src.bot.auth import require_active_user


@require_active_user
async def _dummy(event: Any, *, user: Any, session: Any = None) -> str:
    return "OK"


def _mock_message() -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.answer = AsyncMock()
    return msg


def _mock_query() -> MagicMock:
    q = MagicMock(spec=CallbackQuery)
    q.answer = AsyncMock()
    return q


async def test_require_active_user_passes_through_for_active_user_message() -> None:
    message = _mock_message()
    user = MagicMock(is_blocked=False)
    result = await _dummy(message, user=user)
    assert result == "OK"
    message.answer.assert_not_awaited()


async def test_require_active_user_passes_through_for_active_user_callback() -> None:
    query = _mock_query()
    user = MagicMock(is_blocked=False)
    result = await _dummy(query, user=user)
    assert result == "OK"
    query.answer.assert_not_awaited()


async def test_require_active_user_returns_need_start_for_none_user_message() -> None:
    message = _mock_message()
    result = await _dummy(message, user=None)
    assert result is None
    args, _ = message.answer.call_args
    assert args[0] == texts.NEED_START


async def test_require_active_user_returns_need_start_for_none_user_callback() -> None:
    query = _mock_query()
    result = await _dummy(query, user=None)
    assert result is None
    args, kwargs = query.answer.call_args
    assert args[0] == texts.NEED_START
    assert kwargs["show_alert"] is True


async def test_require_active_user_returns_access_denied_for_blocked_user_message() -> None:
    message = _mock_message()
    user = MagicMock(is_blocked=True)
    result = await _dummy(message, user=user)
    assert result is None
    args, _ = message.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_require_active_user_returns_access_denied_for_blocked_user_callback() -> None:
    query = _mock_query()
    user = MagicMock(is_blocked=True)
    result = await _dummy(query, user=user)
    assert result is None
    args, kwargs = query.answer.call_args
    assert args[0] == texts.ACCESS_DENIED
    assert kwargs["show_alert"] is True
