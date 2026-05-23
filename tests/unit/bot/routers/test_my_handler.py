"""Тесты handler'ов «📋 Мои прогнозы» (TASK-014)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from src.bot import texts
from src.bot.callbacks import MyPredictionCb, MyTabCb
from src.bot.routers.my import (
    cmd_my,
    on_my_prediction,
    on_my_tab,
)


def _mock_message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    return message


def _mock_query() -> MagicMock:
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    query.message = msg
    return query


def _mock_event(
    *,
    event_id: int = 42,
    title: str = "Match",
    is_archived: bool = False,
    result_outcome_id: int | None = None,
    outcomes: list[Any] | None = None,
) -> MagicMock:
    event = MagicMock(
        id=event_id,
        title=title,
        category_id=1,
        is_archived=is_archived,
        is_published=True,
        starts_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
        predictions_close_at=datetime(2026, 6, 1, 17, 45, tzinfo=UTC),
        result_outcome_id=result_outcome_id,
    )
    event.outcomes = outcomes or [
        MagicMock(id=10, label="A"),
        MagicMock(id=11, label="B"),
    ]
    return event


def _mock_prediction(
    *,
    event_id: int = 42,
    outcome_id: int = 10,
    is_correct: bool | None = None,
) -> MagicMock:
    return MagicMock(event_id=event_id, outcome_id=outcome_id, is_correct=is_correct)


def _patch_prediction_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    monkeypatch.setattr("src.bot.routers.my.PredictionService", MagicMock(return_value=instance))
    return instance


def _patch_event_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    monkeypatch.setattr("src.bot.routers.my.EventService", MagicMock(return_value=instance))
    return instance


def _patch_stats_service(
    monkeypatch: pytest.MonkeyPatch, return_value: tuple[int, int, float] = (0, 0, 0.0)
) -> MagicMock:
    instance = MagicMock(user_stats=AsyncMock(return_value=return_value))
    monkeypatch.setattr("src.bot.routers.my.StatsService", MagicMock(return_value=instance))
    return instance


# ===== cmd_my =====


async def test_cmd_my_unauthenticated_sends_need_start() -> None:
    message = _mock_message()
    await cmd_my(message, user=None, session=MagicMock())
    args, _ = message.answer.call_args
    assert args[0] == texts.NEED_START


async def test_cmd_my_blocked_sends_access_denied() -> None:
    message = _mock_message()
    user = MagicMock(is_blocked=True)
    await cmd_my(message, user=user, session=MagicMock())
    args, _ = message.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_cmd_my_no_active_predictions_shows_empty_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prediction_service(
        monkeypatch,
        list_active_by_user=AsyncMock(return_value=[]),
        list_archived_by_user=AsyncMock(return_value=[]),
    )
    message = _mock_message()
    user = MagicMock(is_blocked=False, id=7)
    await cmd_my(message, user=user, session=MagicMock())
    args, _ = message.answer.call_args
    body = args[0]
    assert texts.MY_HEADER_ACTIVE in body
    assert texts.MY_NO_ACTIVE in body
    # Статистика на пустой вкладке «Активные» не показывается.
    assert "📊" not in body


async def test_cmd_my_lists_active_predictions(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _mock_event()
    prediction = _mock_prediction()
    _patch_prediction_service(monkeypatch, list_active_by_user=AsyncMock(return_value=[prediction]))
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))

    message = _mock_message()
    user = MagicMock(is_blocked=False, id=7)
    await cmd_my(message, user=user, session=MagicMock())
    args, kwargs = message.answer.call_args
    body = args[0]
    assert texts.MY_HEADER_ACTIVE in body
    assert "Match" in body
    # User chose outcome id=10 → label "A"
    assert "«A»" in body
    assert kwargs["reply_markup"] is not None


# ===== on_my_tab =====


async def test_on_my_tab_switch_to_archive_renders_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event(is_archived=True, result_outcome_id=11)
    prediction = _mock_prediction(outcome_id=10, is_correct=False)
    _patch_prediction_service(
        monkeypatch, list_archived_by_user=AsyncMock(return_value=[prediction])
    )
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_stats_service(monkeypatch, return_value=(3, 5, 60.0))

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyTabCb(tab="archive", page=0)
    await on_my_tab(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    body = args[0]
    assert texts.MY_HEADER_ARCHIVE in body
    # «✓» от prediction.is_correct=False → ❌
    assert "❌" in body
    # Итог события — outcome id=11 = label "B"
    assert "«B»" in body
    assert "3 / 5" in body
    assert "60.0%" in body


async def test_on_my_tab_archive_empty_shows_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prediction_service(monkeypatch, list_archived_by_user=AsyncMock(return_value=[]))
    _patch_stats_service(monkeypatch, return_value=(0, 0, 0.0))

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyTabCb(tab="archive", page=0)
    await on_my_tab(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    body = args[0]
    assert texts.MY_HEADER_ARCHIVE in body
    assert texts.MY_NO_ARCHIVE in body
    assert "0 / 0" in body


async def test_on_my_tab_pagination_uses_page_size_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 8 предсказаний (PAGE_SIZE=7) → значит has_next=True, отрисовано 7.
    events = [_mock_event(event_id=i, title=f"Match{i}") for i in range(8)]
    predictions = [_mock_prediction(event_id=i, outcome_id=10) for i in range(8)]
    list_active = AsyncMock(return_value=predictions)
    _patch_prediction_service(monkeypatch, list_active_by_user=list_active)
    # get_event возвращает event по event_id из аргумента.
    _patch_event_service(
        monkeypatch,
        get_event=AsyncMock(side_effect=[events[i] for i in range(8)]),
    )

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyTabCb(tab="active", page=0)
    await on_my_tab(query, callback_data=cb, user=user, session=MagicMock())

    # limit=PAGE_SIZE+1=8, offset=0
    _args, kwargs = list_active.call_args
    assert kwargs["offset"] == 0
    assert kwargs["limit"] == 8

    args, kw = query.message.edit_text.call_args
    body = args[0]
    # Отрисовано ровно 7 строк (8-я обрезана, страница 0 имеет has_next).
    assert body.count("Match") == 7
    # Кнопок прогнозов в клавиатуре — 7.
    markup = kw["reply_markup"]
    prediction_buttons = [
        btn for row in markup.inline_keyboard for btn in row if btn.text.startswith("Match")
    ]
    assert len(prediction_buttons) == 7


# ===== on_my_prediction =====


async def test_on_my_prediction_calls_render_event_card_with_back_to_my(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render_mock = AsyncMock()
    monkeypatch.setattr("src.bot.routers.events.render_event_card", render_mock)

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyPredictionCb(event_id=42, tab="active")
    await on_my_prediction(query, callback_data=cb, user=user, session=MagicMock())

    render_mock.assert_awaited_once()
    args, kwargs = render_mock.call_args
    # Сигнатура render_event_card(query, event_id, back_button, user, session, *, allow_archived).
    assert args[1] == 42
    back_text, back_cb = args[2]
    assert back_text == "🔙 К моим прогнозам"
    assert isinstance(back_cb, MyTabCb)
    assert back_cb.tab == "active"
    assert kwargs["allow_archived"] is False


async def test_on_my_prediction_archive_tab_allows_archived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render_mock = AsyncMock()
    monkeypatch.setattr("src.bot.routers.events.render_event_card", render_mock)

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyPredictionCb(event_id=42, tab="archive")
    await on_my_prediction(query, callback_data=cb, user=user, session=MagicMock())

    _args, kwargs = render_mock.call_args
    assert kwargs["allow_archived"] is True


# ===== архивные без зафиксированного итога =====


async def test_archive_row_without_result_uses_pending_emoji(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Событие архивно, но result_outcome_id=None (admin заархивировал без фиксации).
    event = _mock_event(is_archived=True, result_outcome_id=None)
    prediction = _mock_prediction(is_correct=None)
    _patch_prediction_service(
        monkeypatch, list_archived_by_user=AsyncMock(return_value=[prediction])
    )
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_stats_service(monkeypatch, return_value=(0, 0, 0.0))

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = MyTabCb(tab="archive", page=0)
    await on_my_tab(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    body = args[0]
    assert "⏳" in body
    assert "Итог: «—»" in body
