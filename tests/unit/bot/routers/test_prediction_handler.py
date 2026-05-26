"""Тесты handler'ов FSM `MakingPrediction` (TASK-013)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Message
from src.bot import texts
from src.bot.callbacks import (
    PredictCancelCb,
    PredictConfirmCb,
    PredictPickCb,
    PredictStartCb,
)
from src.bot.routers.prediction import (
    cmd_predict,
    on_predict_cancel,
    on_predict_confirm,
    on_predict_pick,
    on_predict_start,
)
from src.bot.states import MakingPrediction
from src.shared.exceptions import (
    EventNotPredictableError,
    OutcomeNotForEventError,
    PredictionDeadlinePassedError,
)


def _mock_query() -> MagicMock:
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.edit_text = AsyncMock()
    query.message = msg
    return query


def _mock_message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    return message


def _mock_state(**data: Any) -> MagicMock:
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value=data)
    return state


def _mock_event(
    *,
    is_published: bool = True,
    is_archived: bool = False,
    minutes_until_close: int = 60,
    outcomes: list[Any] | None = None,
) -> MagicMock:
    event = MagicMock(
        id=42,
        title="Match",
        is_published=is_published,
        is_archived=is_archived,
        predictions_close_at=datetime.now(tz=UTC) + timedelta(minutes=minutes_until_close),
    )
    event.outcomes = outcomes or [
        MagicMock(id=10, label="A"),
        MagicMock(id=11, label="B"),
    ]
    return event


def _patch_event_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    monkeypatch.setattr("src.bot.routers.prediction.EventService", MagicMock(return_value=instance))
    return instance


def _patch_prediction_service(monkeypatch: pytest.MonkeyPatch, **methods: Any) -> MagicMock:
    instance = MagicMock(**methods)
    monkeypatch.setattr(
        "src.bot.routers.prediction.PredictionService",
        MagicMock(return_value=instance),
    )
    return instance


# ===== on_predict_start =====


async def test_predict_start_unauthenticated_returns_alert() -> None:
    query = _mock_query()
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(
        query, callback_data=cb, user=None, session=MagicMock(), state=_mock_state()
    )
    args, kwargs = query.answer.call_args
    assert args[0] == texts.NEED_START
    assert kwargs["show_alert"] is True


async def test_predict_start_blocked_returns_alert() -> None:
    query = _mock_query()
    cb = PredictStartCb(event_id=42, back_category_id=1)
    user = MagicMock(is_blocked=True)
    await on_predict_start(
        query, callback_data=cb, user=user, session=MagicMock(), state=_mock_state()
    )
    args, _ = query.answer.call_args
    assert args[0] == texts.ACCESS_DENIED


async def test_predict_start_event_not_found_clears_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=None))
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE
    state.clear.assert_awaited_once()


async def test_predict_start_event_archived_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(
        monkeypatch, get_event=AsyncMock(return_value=_mock_event(is_archived=True))
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE


async def test_predict_start_event_not_published_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(
        monkeypatch,
        get_event=AsyncMock(return_value=_mock_event(is_published=False)),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.EVENT_NOT_AVAILABLE


async def test_predict_start_deadline_passed_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(
        monkeypatch,
        get_event=AsyncMock(return_value=_mock_event(minutes_until_close=-5)),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.PREDICT_DEADLINE_PASSED


async def test_predict_start_active_event_sets_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=_mock_event()))
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictStartCb(event_id=42, back_category_id=1)
    await on_predict_start(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    state.set_state.assert_awaited_once_with(MakingPrediction.choosing_outcome)
    state.update_data.assert_awaited_once()
    query.message.edit_text.assert_awaited_once()


# ===== on_predict_pick =====


async def test_predict_pick_unknown_outcome_clears_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=_mock_event()))
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictPickCb(event_id=42, outcome_id=999)
    await on_predict_pick(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.PREDICT_OUTCOME_NOT_FOUND
    state.clear.assert_awaited_once()


async def test_predict_pick_valid_outcome_sets_confirming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=_mock_event()))
    query = _mock_query()
    state = _mock_state(back_category_id=1)
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictPickCb(event_id=42, outcome_id=10)
    await on_predict_pick(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    state.set_state.assert_awaited_once_with(MakingPrediction.confirming)
    query.message.edit_text.assert_awaited_once()


# ===== on_predict_confirm =====


async def test_predict_confirm_new_shows_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _mock_event()
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=None),
        make_prediction=AsyncMock(return_value=MagicMock(outcome_id=10)),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictConfirmCb(event_id=42, outcome_id=10)
    await on_predict_confirm(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.PREDICT_SAVED.format(label="A")
    state.clear.assert_awaited_once()


async def test_predict_confirm_existing_shows_updated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _mock_event()
    _patch_event_service(monkeypatch, get_event=AsyncMock(return_value=event))
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=MagicMock(outcome_id=11)),
        make_prediction=AsyncMock(return_value=MagicMock(outcome_id=10)),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictConfirmCb(event_id=42, outcome_id=10)
    await on_predict_confirm(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.message.edit_text.call_args
    assert args[0] == texts.PREDICT_UPDATED.format(label="A")


async def test_predict_confirm_deadline_passed_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=None),
        make_prediction=AsyncMock(side_effect=PredictionDeadlinePassedError("d")),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictConfirmCb(event_id=42, outcome_id=10)
    await on_predict_confirm(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.PREDICT_DEADLINE_PASSED
    state.clear.assert_awaited_once()


async def test_predict_confirm_outcome_not_for_event_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=None),
        make_prediction=AsyncMock(side_effect=OutcomeNotForEventError(event_id=42, outcome_id=999)),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictConfirmCb(event_id=42, outcome_id=999)
    await on_predict_confirm(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.PREDICT_OUTCOME_NOT_FOUND


async def test_predict_confirm_event_not_predictable_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_prediction_service(
        monkeypatch,
        get_user_prediction=AsyncMock(return_value=None),
        make_prediction=AsyncMock(side_effect=EventNotPredictableError(reason="archived")),
    )
    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictConfirmCb(event_id=42, outcome_id=10)
    await on_predict_confirm(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    args, _ = query.answer.call_args
    assert args[0] == texts.PREDICT_EVENT_UNAVAILABLE


# ===== on_predict_cancel =====


async def test_predict_cancel_clears_state_and_returns_to_event_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # render_event_card вызывается; патчим, чтобы не лезть в EventService.
    render_mock = AsyncMock()
    monkeypatch.setattr("src.bot.routers.events.render_event_card", render_mock)

    query = _mock_query()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    cb = PredictCancelCb(event_id=42, back_category_id=1)
    await on_predict_cancel(query, callback_data=cb, user=user, session=MagicMock(), state=state)
    state.clear.assert_awaited_once()
    render_mock.assert_awaited_once()


# ===== cmd_predict =====


async def test_cmd_predict_delegates_to_cmd_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd_events_mock = AsyncMock()
    monkeypatch.setattr("src.bot.routers.events.cmd_events", cmd_events_mock)
    message = _mock_message()
    state = _mock_state()
    user = MagicMock(is_blocked=False, id=7)
    await cmd_predict(message, user=user, session=MagicMock(), state=state)
    state.clear.assert_awaited_once()
    cmd_events_mock.assert_awaited_once()
