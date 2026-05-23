"""Integration-тесты `EventService`."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import (
    EventAlreadyHasResultError,
    EventNotEnoughOutcomesError,
    EventNotFoundError,
    OutcomeInUseError,
    OutcomeNotForEventError,
)
from src.shared.models import AuditLog, Prediction
from src.shared.services import EventService
from tests.integration.conftest import (
    make_admin,
    make_event,
    make_outcome,
    make_user,
)

pytestmark = pytest.mark.integration


async def test_publish_event_no_outcomes_raises(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    with pytest.raises(EventNotEnoughOutcomesError):
        await service.publish_event(event.id, admin.id)


async def test_publish_event_one_outcome_raises(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    await make_outcome(nested_session, event.id)
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    with pytest.raises(EventNotEnoughOutcomesError):
        await service.publish_event(event.id, admin.id)


async def test_publish_event_two_outcomes_writes_audit(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    await make_outcome(nested_session, event.id, label="A")
    await make_outcome(nested_session, event.id, label="B")
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    await service.publish_event(event.id, admin.id)

    await nested_session.refresh(event)
    assert event.is_published is True

    entry = (
        await nested_session.execute(
            select(AuditLog).where(AuditLog.action == "event.publish").order_by(AuditLog.id.desc())
        )
    ).scalar_one_or_none()
    assert entry is not None
    assert entry.payload == {"event_id": event.id}


async def test_set_result_marks_predictions_and_archives(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    correct = await make_outcome(nested_session, event.id, label="correct")
    wrong = await make_outcome(nested_session, event.id, label="wrong")
    u1 = await make_user(nested_session)
    u2 = await make_user(nested_session)
    nested_session.add(Prediction(user_id=u1.id, event_id=event.id, outcome_id=correct.id))
    nested_session.add(Prediction(user_id=u2.id, event_id=event.id, outcome_id=wrong.id))
    await nested_session.flush()
    admin = await make_admin(nested_session)

    service = EventService(nested_session)
    marked = await service.set_result(event.id, correct.id, admin.id)
    assert marked == 2

    await nested_session.refresh(event)
    assert event.is_archived is True
    assert event.result_outcome_id == correct.id
    assert event.archived_at is not None

    preds = (
        (await nested_session.execute(select(Prediction).where(Prediction.event_id == event.id)))
        .scalars()
        .all()
    )
    assert {p.is_correct for p in preds if p.user_id == u1.id} == {True}
    assert {p.is_correct for p in preds if p.user_id == u2.id} == {False}


async def test_set_result_twice_raises(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    o1 = await make_outcome(nested_session, event.id, label="A")
    await make_outcome(nested_session, event.id, label="B")
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    await service.set_result(event.id, o1.id, admin.id)
    with pytest.raises(EventAlreadyHasResultError):
        await service.set_result(event.id, o1.id, admin.id)


async def test_set_result_foreign_outcome_raises(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    await make_outcome(nested_session, event.id, label="A")
    other_event = await make_event(nested_session)
    foreign = await make_outcome(nested_session, other_event.id, label="X")
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    with pytest.raises(OutcomeNotForEventError):
        await service.set_result(event.id, foreign.id, admin.id)


async def test_set_result_event_not_found(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    with pytest.raises(EventNotFoundError):
        await service.set_result(999_999, 1, admin.id)


async def test_delete_outcome_in_use_raises(
    nested_session: AsyncSession,
) -> None:
    event = await make_event(nested_session)
    outcome = await make_outcome(nested_session, event.id, label="X")
    user = await make_user(nested_session)
    nested_session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await nested_session.flush()
    admin = await make_admin(nested_session)
    service = EventService(nested_session)
    with pytest.raises(OutcomeInUseError):
        await service.delete_outcome(outcome.id, admin.id)
