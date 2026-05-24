"""Тесты handler'ов `/reminders` (TASK-015)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from src.bot import texts
from src.bot.callbacks import (
    PresetOffsetCb,
    RemoveOffsetCb,
)
from src.bot.routers.reminders import (
    cmd_reminders,
    on_add_offset,
    on_custom_offset,
    on_custom_offset_input,
    on_preset_offset,
    on_remove_offset,
    on_toggle_reminders,
)
from src.bot.states import EditingReminders
from src.shared.exceptions import InvalidReminderOffsetsError


def _mock_message(text: str | None = None) -> MagicMock:
    msg = MagicMock(spec=Message)
    msg.answer = AsyncMock()
    msg.text = text
    return msg


def _mock_query() -> MagicMock:
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    query.message = msg
    return query


def _mock_state() -> MagicMock:
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    return state


def _mock_setting(*, enabled: bool = True, offsets: list[int] | None = None) -> MagicMock:
    s = MagicMock()
    s.enabled = enabled
    s.offsets_minutes = offsets if offsets is not None else [1440, 60]
    return s


def _patch_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    setting: Any | None = None,
    refreshed: Any | None = None,
    update_side_effect: Exception | None = None,
) -> MagicMock:
    """Mock `ReminderService` — `get` возвращает setting/refreshed по очереди, update — AsyncMock."""
    if refreshed is None:
        refreshed = setting
    instance = MagicMock()
    # Первый get → исходный setting, второй → обновлённый.
    instance.get = AsyncMock(side_effect=[setting, refreshed, refreshed])
    if update_side_effect is not None:
        instance.update = AsyncMock(side_effect=update_side_effect)
    else:
        instance.update = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(
        "src.bot.routers.reminders.ReminderService", MagicMock(return_value=instance)
    )
    return instance


# ===== cmd_reminders =====


async def test_cmd_reminders_unauthenticated_returns_message() -> None:
    msg = _mock_message()
    await cmd_reminders(msg, user=None, session=MagicMock(), state=_mock_state())
    args, _ = msg.answer.call_args
    assert args[0] == texts.NEED_START


async def test_cmd_reminders_blocked_returns_message() -> None:
    msg = _mock_message()
    user = MagicMock(is_blocked=True)
    await cmd_reminders(msg, user=user, session=MagicMock(), state=_mock_state())
    args, _ = msg.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_cmd_reminders_enabled_with_offsets_renders_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_service(monkeypatch, setting=_mock_setting(enabled=True, offsets=[1440, 60]))
    msg = _mock_message()
    user = MagicMock(is_blocked=False, id=7)
    await cmd_reminders(msg, user=user, session=MagicMock(), state=_mock_state())
    args, kwargs = msg.answer.call_args
    text = args[0]
    assert texts.REMINDERS_HEADER in text
    assert texts.REMINDERS_STATUS_ENABLED in text
    assert "1 д" in text and "1 ч" in text  # humanize
    assert kwargs["reply_markup"] is not None


async def test_cmd_reminders_disabled_renders_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_service(monkeypatch, setting=_mock_setting(enabled=False, offsets=[1440, 60]))
    msg = _mock_message()
    user = MagicMock(is_blocked=False, id=7)
    await cmd_reminders(msg, user=user, session=MagicMock(), state=_mock_state())
    args, _ = msg.answer.call_args
    text = args[0]
    assert texts.REMINDERS_STATUS_DISABLED in text
    assert texts.REMINDERS_HINT_DISABLED in text


# ===== on_toggle_reminders =====


async def test_on_toggle_inverts_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _patch_service(
        monkeypatch,
        setting=_mock_setting(enabled=True, offsets=[60]),
        refreshed=_mock_setting(enabled=False, offsets=[60]),
    )
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    await on_toggle_reminders(query, user=user, session=MagicMock())
    instance.update.assert_awaited_once()
    kwargs = instance.update.call_args.kwargs
    assert kwargs["enabled"] is False
    query.message.edit_text.assert_awaited_once()


# ===== on_add_offset =====


async def test_on_add_offset_shows_presets() -> None:
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    await on_add_offset(query, user=user, session=MagicMock())
    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.REMINDERS_ADD_PROMPT


# ===== on_preset_offset =====


async def test_on_preset_offset_adds_to_list(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _patch_service(
        monkeypatch,
        setting=_mock_setting(enabled=True, offsets=[1440]),
        refreshed=_mock_setting(enabled=True, offsets=[1440, 60]),
    )
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    await on_preset_offset(
        query, callback_data=PresetOffsetCb(minutes=60), user=user, session=MagicMock()
    )
    instance.update.assert_awaited_once()
    new_offsets = instance.update.call_args.kwargs["offsets_minutes"]
    assert 60 in new_offsets
    assert 1440 in new_offsets


async def test_on_preset_offset_too_many_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_service(
        monkeypatch,
        setting=_mock_setting(enabled=True, offsets=[15, 30, 60, 180, 720]),
        update_side_effect=InvalidReminderOffsetsError(
            "too many offsets: 6 (max 5)", reason="too_many"
        ),
    )
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    await on_preset_offset(
        query, callback_data=PresetOffsetCb(minutes=1440), user=user, session=MagicMock()
    )
    args, kwargs = query.answer.call_args
    assert args[0] == texts.REMINDERS_ERR_TOO_MANY
    assert kwargs["show_alert"] is True


# ===== on_custom_offset / on_custom_offset_input =====


async def test_on_custom_offset_sets_state_and_asks_input() -> None:
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    await on_custom_offset(query, user=user, session=MagicMock(), state=state)
    state.set_state.assert_awaited_once_with(EditingReminders.adding_offset)
    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.REMINDERS_ASK_CUSTOM


async def test_on_custom_offset_input_valid_adds_and_clears_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_service(
        monkeypatch,
        setting=_mock_setting(enabled=True, offsets=[60]),
        refreshed=_mock_setting(enabled=True, offsets=[60, 90]),
    )
    msg = _mock_message("90m")
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    await on_custom_offset_input(msg, user=user, session=MagicMock(), state=state)
    state.clear.assert_awaited_once()
    args, _ = msg.answer.call_args
    assert "1 ч 30 мин" in args[0]


async def test_on_custom_offset_input_invalid_keeps_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msg = _mock_message("garbage")
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    await on_custom_offset_input(msg, user=user, session=MagicMock(), state=state)
    state.clear.assert_not_awaited()
    args, _ = msg.answer.call_args
    assert args[0] == texts.REMINDERS_INVALID_INPUT


# ===== on_remove_offset =====


async def test_on_remove_offset_removes_from_list(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _patch_service(
        monkeypatch,
        setting=_mock_setting(enabled=True, offsets=[60, 1440]),
        refreshed=_mock_setting(enabled=True, offsets=[1440]),
    )
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    await on_remove_offset(
        query, callback_data=RemoveOffsetCb(minutes=60), user=user, session=MagicMock()
    )
    new_offsets = instance.update.call_args.kwargs["offsets_minutes"]
    assert 60 not in new_offsets
    assert 1440 in new_offsets
