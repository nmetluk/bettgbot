"""Integration-тесты `UserService.list_admin_with_counts` (TASK-025)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import UserService
from tests.integration.conftest import (
    make_admin,
    make_category,
    make_event,
    make_outcome,
    make_user,
)

pytestmark = pytest.mark.integration


async def test_list_admin_with_counts_returns_predictions_count(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    user = await make_user(nested_session, tg_username="alice-int")
    event = await make_event(nested_session, category=category, admin=admin)
    outcome = await make_outcome(nested_session, event_id=event.id)
    for _ in range(3):
        ev = await make_event(nested_session, category=category, admin=admin)
        out = await make_outcome(nested_session, event_id=ev.id)
        nested_session.add(Prediction(user_id=user.id, event_id=ev.id, outcome_id=out.id))
    # Один прогноз на исходное event (всего 4 предсказания у user).
    nested_session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await nested_session.flush()

    rows = await UserService(nested_session).list_admin_with_counts(query="alice-int")

    found = [(u, n) for (u, n) in rows if u.id == user.id]
    assert len(found) == 1
    assert found[0][1] == 4


async def test_list_admin_with_counts_filter_by_phone_substring(
    nested_session: AsyncSession,
) -> None:
    matching = await make_user(nested_session, phone="+79991234567")
    await make_user(nested_session, phone="+78881234567")

    rows = await UserService(nested_session).list_admin_with_counts(query="999")

    ids = {u.id for u, _ in rows}
    assert matching.id in ids
    assert all("999" in u.phone for u, _ in rows)


async def test_list_admin_with_counts_filter_by_username(
    nested_session: AsyncSession,
) -> None:
    target = await make_user(nested_session, tg_username="bob-unique-int")
    await make_user(nested_session, tg_username="other-int")

    rows = await UserService(nested_session).list_admin_with_counts(query="bob-unique")

    ids = {u.id for u, _ in rows}
    assert target.id in ids


async def test_list_admin_with_counts_includes_blocked_users(
    nested_session: AsyncSession,
) -> None:
    blocked = await make_user(nested_session, is_blocked=True, tg_username="blocked-int")

    rows = await UserService(nested_session).list_admin_with_counts(query="blocked-int")

    assert any(u.id == blocked.id and u.is_blocked for u, _ in rows)
