"""Integration-тесты `StatsService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import StatsService
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_stats_empty_user(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = StatsService(nested_session)
    assert await service.user_stats(user.id) == (0, 0, 0.0)


async def test_stats_2_correct_of_5(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = StatsService(nested_session)

    # 5 событий с прогнозом, 2 — верных.
    for i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        pred = Prediction(
            user_id=user.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=(i < 2),
        )
        nested_session.add(pred)
    await nested_session.flush()

    correct, total, percent = await service.user_stats(user.id)
    assert correct == 2
    assert total == 5
    assert percent == 40.0
