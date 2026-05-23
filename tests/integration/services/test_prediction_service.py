"""Integration-тесты `PredictionService`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import (
    EventNotPredictableError,
    OutcomeNotForEventError,
    PredictionDeadlinePassedError,
)
from src.shared.services import PredictionService
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def _published_open(session: AsyncSession) -> object:
    return await make_event(
        session,
        is_published=True,
        is_archived=False,
        starts_at=datetime.now(tz=UTC) + timedelta(hours=2),
        predictions_close_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )


async def test_make_prediction_happy(nested_session: AsyncSession) -> None:
    event = await _published_open(nested_session)
    outcome = await make_outcome(nested_session, event.id)
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    pred = await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id)
    assert pred.outcome_id == outcome.id


async def test_make_prediction_upsert_updates(nested_session: AsyncSession) -> None:
    event = await _published_open(nested_session)
    o1 = await make_outcome(nested_session, event.id, label="A")
    o2 = await make_outcome(nested_session, event.id, label="B")
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    first = await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=o1.id)
    second = await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=o2.id)
    assert second.id == first.id
    assert second.outcome_id == o2.id


async def test_event_archived(nested_session: AsyncSession) -> None:
    # CHECK `ck_event_result_archive_consistency` требует синхронности
    # `result_outcome_id`/`is_archived`/`archived_at`. Делаем archived event как
    # его делает сервис set_result: event → outcome → выставляем все три поля.
    event = await make_event(nested_session, is_published=True)
    outcome = await make_outcome(nested_session, event.id)
    event.is_archived = True
    event.result_outcome_id = outcome.id
    event.archived_at = datetime.now(tz=UTC)
    await nested_session.flush()

    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    with pytest.raises(EventNotPredictableError) as exc:
        await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id)
    assert exc.value.reason == "archived"


async def test_event_not_published(nested_session: AsyncSession) -> None:
    event = await make_event(nested_session, is_published=False)
    outcome = await make_outcome(nested_session, event.id)
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    with pytest.raises(EventNotPredictableError) as exc:
        await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id)
    assert exc.value.reason == "not_published"


async def test_event_not_found(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    with pytest.raises(EventNotPredictableError) as exc:
        await service.make_prediction(user_id=user.id, event_id=999_999, outcome_id=1)
    assert exc.value.reason == "not_found"


async def test_deadline_passed(nested_session: AsyncSession) -> None:
    past = datetime.now(tz=UTC) - timedelta(minutes=1)
    event = await make_event(
        nested_session,
        is_published=True,
        is_archived=False,
        starts_at=past + timedelta(seconds=1),
        predictions_close_at=past,
    )
    outcome = await make_outcome(nested_session, event.id)
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    with pytest.raises(PredictionDeadlinePassedError):
        await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id)


async def test_outcome_not_for_event(nested_session: AsyncSession) -> None:
    event = await _published_open(nested_session)
    await make_outcome(nested_session, event.id, label="A")
    other = await _published_open(nested_session)
    foreign = await make_outcome(nested_session, other.id, label="X")
    user = await make_user(nested_session)
    service = PredictionService(nested_session)
    with pytest.raises(OutcomeNotForEventError):
        await service.make_prediction(user_id=user.id, event_id=event.id, outcome_id=foreign.id)
