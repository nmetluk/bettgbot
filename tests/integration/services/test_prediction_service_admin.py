"""Integration-тесты `PredictionService.list_all_by_user_for_admin` (TASK-025)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import PredictionService
from tests.integration.conftest import (
    make_admin,
    make_category,
    make_event,
    make_outcome,
    make_user,
)

pytestmark = pytest.mark.integration


async def test_list_all_by_user_for_admin_returns_active_and_archived(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    user = await make_user(nested_session)

    # Активный event + prediction.
    active = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now + timedelta(days=2),
        predictions_close_at=now + timedelta(days=1),
        is_published=True,
    )
    active_out = await make_outcome(nested_session, event_id=active.id)
    nested_session.add(Prediction(user_id=user.id, event_id=active.id, outcome_id=active_out.id))

    # Архивный event (с result) + prediction.
    archived = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now - timedelta(days=10),
        predictions_close_at=now - timedelta(days=11),
        is_published=True,
    )
    archived_out = await make_outcome(nested_session, event_id=archived.id)
    archived.result_outcome_id = archived_out.id
    archived.is_archived = True
    archived.archived_at = now - timedelta(days=9)
    nested_session.add(
        Prediction(user_id=user.id, event_id=archived.id, outcome_id=archived_out.id)
    )
    await nested_session.flush()

    predictions = await PredictionService(nested_session).list_all_by_user_for_admin(user.id)

    event_ids = {p.event_id for p in predictions}
    assert active.id in event_ids
    assert archived.id in event_ids


async def test_list_all_by_user_for_admin_eager_loads_event_and_outcome(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    user = await make_user(nested_session)
    event = await make_event(nested_session, category=category, admin=admin, title="Eager Test")
    outcome = await make_outcome(nested_session, event_id=event.id, label="Win")
    nested_session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await nested_session.flush()

    predictions = await PredictionService(nested_session).list_all_by_user_for_admin(user.id)

    assert len(predictions) == 1
    p = predictions[0]
    # Eager loaded — никакого implicit lazy IO.
    assert p.event.title == "Eager Test"
    assert p.outcome.label == "Win"
