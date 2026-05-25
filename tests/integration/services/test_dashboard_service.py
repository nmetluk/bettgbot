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
    # пустая БД — все нули
    assert counters == {"users": 0, "events": 0, "categories": 0, "predictions": 0}


async def test_get_counters_counts_actual_records(session: AsyncSession) -> None:
    """Счётчики считают реальные записи в БД."""
    # создаём данные
    await make_user(session)
    await make_user(session)

    await make_category(session)
    await make_category(session, is_active=False)

    await make_event(session)
    await make_event(session)

    user = await make_user(session)
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)

    pred_repo = PredictionRepository(session)
    await pred_repo.upsert(user_id=user.id, event_id=event.id, outcome_id=outcome.id)

    service = DashboardService(session)
    counters = await service.get_counters()

    assert counters["users"] == 3
    assert counters["categories"] == 2
    assert counters["events"] == 3
    assert counters["predictions"] == 1
