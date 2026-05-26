"""Integration-тесты `OutcomeRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.repositories import OutcomeRepository
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_list_by_event_sorted_by_sort_order(session: AsyncSession) -> None:
    event = await make_event(session)
    o1 = await make_outcome(session, event.id, label="A", sort_order=2)
    o2 = await make_outcome(session, event.id, label="B", sort_order=1)
    repo = OutcomeRepository(session)
    ordered = await repo.list_by_event(event.id)
    assert [o.id for o in ordered] == [o2.id, o1.id]


async def test_count_by_event(session: AsyncSession) -> None:
    event = await make_event(session)
    await make_outcome(session, event.id)
    await make_outcome(session, event.id)
    repo = OutcomeRepository(session)
    assert await repo.count_by_event(event.id) == 2


async def test_delete_restricted_by_prediction(session: AsyncSession) -> None:
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    user = await make_user(session)
    session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await session.flush()

    repo = OutcomeRepository(session)
    with pytest.raises(IntegrityError):
        await repo.delete(event.id, outcome.id)
        await session.flush()
