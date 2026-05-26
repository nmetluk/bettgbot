"""Integration-тесты `DashboardService` (TASK-043)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import PredictionRepository
from src.shared.services import DashboardService
from tests.integration.conftest import make_category, make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_get_counters_returns_all_four(session: AsyncSession) -> None:
    """Счётчики возвращают dict с ключами users, events, categories, predictions."""
    service = DashboardService(session)
    counters = await service.get_counters()

    assert set(counters.keys()) == {"users", "events", "categories", "predictions"}


async def test_get_counters_increments(session: AsyncSession) -> None:
    """Счётчики увеличиваются при добавлении записей."""
    service = DashboardService(session)

    before = await service.get_counters()
    initial_users = before["users"]
    initial_categories = before["categories"]
    initial_events = before["events"]
    initial_predictions = before["predictions"]

    # добавляем записи
    await make_user(session)
    await make_category(session)
    await make_event(session)
    user = await make_user(session)
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)

    pred_repo = PredictionRepository(session)
    await pred_repo.upsert(user_id=user.id, event_id=event.id, outcome_id=outcome.id)

    after = await service.get_counters()
    assert after["users"] == initial_users + 2
    assert after["categories"] == initial_categories + 1
    assert after["events"] == initial_events + 2
    assert after["predictions"] == initial_predictions + 1
