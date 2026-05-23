"""Тесты handler'ов `/events` и связанных callback'ов (TASK-012)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.bot import texts
from src.bot.callbacks import CategoryCb, CategoryListCb, EventCb
from src.bot.routers.events import (
    cmd_events,
    on_back_to_categories,
    on_category,
    on_event,
)


def _mock_message() -> MagicMock:
    message = MagicMock()
    message.answer = AsyncMock()
    return message


def _mock_query(message: Any | None = None) -> MagicMock:
    query = MagicMock()
    query.answer = AsyncMock()
    # query.message — настоящий aiogram.types.Message; используем реальный класс
    # для прохождения isinstance-check в handler'е.
    from aiogram.types import Message

    if message is None:
        message = MagicMock(spec=Message)
        message.edit_text = AsyncMock()
    query.message = message
    return query


def _patch_event_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr("src.bot.routers.events.EventService", factory)
    return instance


def _patch_category_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr("src.bot.routers.events.CategoryService", factory)
    return instance


def _patch_prediction_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    factory = MagicMock(return_value=instance)
    monkeypatch.setattr("src.bot.routers.events.PredictionService", factory)
    return instance


# ===== cmd_events =====


async def test_cmd_events_unauthenticated_sends_need_start() -> None:
    message = _mock_message()
    await cmd_events(message, user=None, session=MagicMock())
    args, _ = message.answer.call_args
    assert args[0] == texts.NEED_START


async def test_cmd_events_blocked_sends_access_denied() -> None:
    message = _mock_message()
    user = MagicMock(is_blocked=True)
    await cmd_events(message, user=user, session=MagicMock())
    args, _ = message.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_cmd_events_no_categories_sends_no_events_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(
        monkeypatch,
        list_categories_with_counts=AsyncMock(return_value=([], 0)),
    )
    message = _mock_message()
    user = MagicMock(is_blocked=False)
    await cmd_events(message, user=user, session=MagicMock())
    args, _ = message.answer.call_args
    assert args[0] == texts.NO_EVENTS_AT_ALL


async def test_cmd_events_lists_categories_with_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cat = MagicMock(id=1, name="Football")
    _patch_event_service(
        monkeypatch,
        list_categories_with_counts=AsyncMock(return_value=([(cat, 3)], 3)),
    )
    message = _mock_message()
    user = MagicMock(is_blocked=False)
    await cmd_events(message, user=user, session=MagicMock())
    args, kwargs = message.answer.call_args
    assert args[0] == texts.CATEGORIES_PROMPT
    assert kwargs["reply_markup"] is not None


# ===== on_category =====


async def test_on_category_lists_events_with_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        MagicMock(
            id=i,
            title=f"Event{i}",
            starts_at=datetime.now(tz=UTC) + timedelta(hours=i),
        )
        for i in range(8)
    ]
    _patch_event_service(monkeypatch, list_active=AsyncMock(return_value=events))
    _patch_category_service(monkeypatch, get_by_id=AsyncMock(return_value=MagicMock(name="Cat")))

    query = _mock_query()
    user = MagicMock(is_blocked=False)
    cb = CategoryCb(category_id=1, page=0)
    await on_category(query, callback_data=cb, user=user, session=MagicMock())

    query.message.edit_text.assert_awaited_once()
    query.answer.assert_awaited_once()


async def test_on_category_empty_shows_no_events_in_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, list_active=AsyncMock(return_value=[]))
    query = _mock_query()
    user = MagicMock(is_blocked=False)
    cb = CategoryCb(category_id=1, page=0)
    await on_category(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.NO_EVENTS_IN_CATEGORY


async def test_on_back_to_categories_navigates_to_category_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(
        monkeypatch,
        list_categories_with_counts=AsyncMock(return_value=([], 0)),
    )
    query = _mock_query()
    user = MagicMock(is_blocked=False)
    await on_back_to_categories(query, user=user, session=MagicMock())
    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.CATEGORIES_PROMPT


# ===== on_event =====


def _mock_event(
    *,
    outcomes: list[Any] | None = None,
    is_published: bool = True,
    is_archived: bool = False,
) -> MagicMock:
    event = MagicMock(
        id=42,
        title="Match",
        description=None,
        starts_at=datetime(2026, 6, 1, 18, 0, tzinfo=UTC),
        predictions_close_at=datetime(2026, 6, 1, 17, 45, tzinfo=UTC),
        category_id=1,
        is_published=is_published,
        is_archived=is_archived,
    )
    event.outcomes = outcomes or [
        MagicMock(id=10, label="A"),
        MagicMock(id=11, label="B"),
    ]
    return event


async def test_on_event_renders_card_without_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event()
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_category_service(monkeypatch, get_by_id=AsyncMock(return_value=MagicMock(name="Cat")))
    _patch_prediction_service(monkeypatch, get_user_prediction=AsyncMock(return_value=None))

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = EventCb(event_id=42, back_category_id=1)
    await on_event(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    text = args[0]
    assert "Match" in text
    assert "A" in text and "B" in text
    assert "Ваш прогноз" not in text


async def test_on_event_renders_card_with_user_prediction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event()
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_category_service(monkeypatch, get_by_id=AsyncMock(return_value=MagicMock(name="Cat")))
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=MagicMock(outcome_id=11)),
    )

    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = EventCb(event_id=42, back_category_id=1)
    await on_event(query, callback_data=cb, user=user, session=MagicMock())

    args, _ = query.message.edit_text.call_args
    text = args[0]
    assert "Ваш прогноз" in text
    assert "«B»" in text


async def test_on_event_archived_returns_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event(is_archived=True)
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = EventCb(event_id=42, back_category_id=1)
    await on_event(query, callback_data=cb, user=user, session=MagicMock())
    args, kwargs = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE
    assert kwargs["show_alert"] is True


async def test_on_event_not_published_returns_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event(is_published=False)
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = EventCb(event_id=42, back_category_id=1)
    await on_event(query, callback_data=cb, user=user, session=MagicMock())
    args, _kwargs = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE


async def test_on_event_not_found_returns_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=None))
    query = _mock_query()
    user = MagicMock(is_blocked=False, id=7)
    cb = EventCb(event_id=999, back_category_id=1)
    await on_event(query, callback_data=cb, user=user, session=MagicMock())
    args, _ = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE


# ===== auth для callback'ов =====


async def test_callback_unauthenticated_uses_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = _mock_query()
    # callback_data для on_back_to_categories aiogram пробрасывает автоматически;
    # вызываем функцию напрямую без него.
    await on_back_to_categories(query, user=None, session=MagicMock())
    args, kwargs = query.answer.call_args
    assert args[0] == texts.NEED_START
    assert kwargs["show_alert"] is True
