"""Integration-тесты `PredictionRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import PredictionRepository
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_upsert_inserts_then_updates(session: AsyncSession) -> None:
    event = await make_event(session)
    o1 = await make_outcome(session, event.id, label="A")
    o2 = await make_outcome(session, event.id, label="B")
    user = await make_user(session)
    repo = PredictionRepository(session)

    inserted = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o1.id)
    assert inserted.outcome_id == o1.id

    updated = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o2.id)
    assert updated.id == inserted.id
    assert updated.outcome_id == o2.id


async def test_mark_correctness_sets_true_false(session: AsyncSession) -> None:
    event = await make_event(session)
    correct = await make_outcome(session, event.id, label="correct")
    wrong = await make_outcome(session, event.id, label="wrong")

    u1 = await make_user(session)
    u2 = await make_user(session)
    repo = PredictionRepository(session)
    await repo.upsert(user_id=u1.id, event_id=event.id, outcome_id=correct.id)
    await repo.upsert(user_id=u2.id, event_id=event.id, outcome_id=wrong.id)

    rowcount = await repo.mark_correctness(event.id, correct.id)
    assert rowcount == 2

    p1 = await repo.get_by_user_event(u1.id, event.id)
    p2 = await repo.get_by_user_event(u2.id, event.id)
    assert p1 is not None and p1.is_correct is True
    assert p2 is not None and p2.is_correct is False


async def test_user_stats(session: AsyncSession) -> None:
    event = await make_event(session)
    o = await make_outcome(session, event.id, label="X")
    user = await make_user(session)
    repo = PredictionRepository(session)
    pred = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o.id)

    correct, total = await repo.user_stats(user.id)
    assert correct == 0 and total == 0

    pred.is_correct = True
    await session.flush()
    correct, total = await repo.user_stats(user.id)
    assert correct == 1 and total == 1


async def test_list_active_and_archived(session: AsyncSession) -> None:
    user = await make_user(session)
    active_event = await make_event(session, is_archived=False)
    o1 = await make_outcome(session, active_event.id)
    repo = PredictionRepository(session)
    await repo.upsert(user_id=user.id, event_id=active_event.id, outcome_id=o1.id)

    active = await repo.list_active_by_user(user.id)
    assert any(p.event_id == active_event.id for p in active)
    archived = await repo.list_archived_by_user(user.id)
    assert all(p.event_id != active_event.id for p in archived)


async def test_users_without_prediction_for_event(session: AsyncSession) -> None:
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    u_with = await make_user(session)
    u_without = await make_user(session)
    u_blocked = await make_user(session, is_blocked=True)

    repo = PredictionRepository(session)
    await repo.upsert(user_id=u_with.id, event_id=event.id, outcome_id=outcome.id)

    ids = await repo.users_without_prediction_for_event(event.id)
    assert u_without.id in ids
    assert u_with.id not in ids
    assert u_blocked.id not in ids


async def test_count_returns_total_predictions(session: AsyncSession) -> None:
    """Счётчик возвращает общее количество прогнозов."""
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    u1 = await make_user(session)
    u2 = await make_user(session)

    repo = PredictionRepository(session)
    await repo.upsert(user_id=u1.id, event_id=event.id, outcome_id=outcome.id)
    await repo.upsert(user_id=u2.id, event_id=event.id, outcome_id=outcome.id)

    assert await repo.count() == 2
