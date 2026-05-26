"""Integration-тесты `EventService.list_admin_with_counts` + фильтры (TASK-022)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import EventService
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
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=True,
    )
    outcome = await make_outcome(nested_session, event_id=event.id)
    for _ in range(3):
        user = await make_user(nested_session)
        nested_session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await nested_session.flush()

    rows = await EventService(nested_session).list_admin_with_counts(category_id=category.id)

    found = [(e, n) for (e, n) in rows if e.id == event.id]
    assert len(found) == 1
    assert found[0][1] == 3


async def test_list_admin_with_counts_filter_by_category(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    cat_a = await make_category(nested_session)
    cat_b = await make_category(nested_session)
    event_a = await make_event(nested_session, category=cat_a, admin=admin)
    await make_event(nested_session, category=cat_b, admin=admin)

    rows = await EventService(nested_session).list_admin_with_counts(category_id=cat_a.id)

    assert all(e.category_id == cat_a.id for e, _ in rows)
    assert any(e.id == event_a.id for e, _ in rows)


async def test_list_admin_with_counts_filter_status_draft(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    draft = await make_event(nested_session, category=category, admin=admin, is_published=False)
    await make_event(nested_session, category=category, admin=admin, is_published=True)

    rows = await EventService(nested_session).list_admin_with_counts(
        category_id=category.id, status="draft"
    )

    ids = {e.id for e, _ in rows}
    assert draft.id in ids
    assert all(not e.is_published for e, _ in rows)


async def test_list_admin_with_counts_filter_status_published_open(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    open_event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=True,
        starts_at=now + timedelta(days=2),
        predictions_close_at=now + timedelta(days=1),
    )
    await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=True,
        starts_at=now - timedelta(days=1),
        predictions_close_at=now - timedelta(days=2),
    )

    rows = await EventService(nested_session).list_admin_with_counts(
        category_id=category.id, status="published_open"
    )

    ids = {e.id for e, _ in rows}
    assert open_event.id in ids
    assert all(e.is_published and e.predictions_close_at > now for e, _ in rows)


async def test_list_admin_with_counts_filter_period_next7(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    near = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now + timedelta(days=3),
        predictions_close_at=now + timedelta(days=2),
    )
    await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now + timedelta(days=20),
        predictions_close_at=now + timedelta(days=19),
    )

    rows = await EventService(nested_session).list_admin_with_counts(
        category_id=category.id, period="next7"
    )

    ids = {e.id for e, _ in rows}
    assert near.id in ids
    assert all(now <= e.starts_at < now + timedelta(days=7) for e, _ in rows)


async def test_list_admin_with_counts_filter_period_past(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    past_event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now - timedelta(days=2),
        predictions_close_at=now - timedelta(days=3),
    )
    await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=now + timedelta(days=2),
        predictions_close_at=now + timedelta(days=1),
    )

    rows = await EventService(nested_session).list_admin_with_counts(
        category_id=category.id, period="past"
    )

    ids = {e.id for e, _ in rows}
    assert past_event.id in ids
    assert all(e.starts_at < now for e, _ in rows)


async def test_count_admin_matches_list_length(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    for _ in range(3):
        await make_event(nested_session, category=category, admin=admin)

    service = EventService(nested_session)
    rows = await service.list_admin_with_counts(category_id=category.id)
    total = await service.count_admin(category_id=category.id)

    assert total == len(rows)


async def test_update_outcome_with_correct_event_id_succeeds(
    nested_session: AsyncSession,
) -> None:
    """update_outcom с правильным event_id успешно обновляет исход."""
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event = await make_event(nested_session, category=category, admin=admin)
    outcome = await make_outcome(nested_session, event_id=event.id, label="Old Label")

    service = EventService(nested_session)
    await service.update_outcome(
        outcome_id=outcome.id, event_id=event.id, by_admin_id=admin.id, label="New Label"
    )

    await nested_session.flush()
    updated = await service._outcomes.get_by_id(outcome.id)
    assert updated is not None
    assert updated.label == "New Label"


async def test_update_outcome_with_wrong_event_id_raises(
    nested_session: AsyncSession,
) -> None:
    """update_outcome с чужим event_id поднимает OutcomeNotForEventError."""
    from src.shared.exceptions import OutcomeNotForEventError

    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event1 = await make_event(nested_session, category=category, admin=admin)
    event2 = await make_event(nested_session, category=category, admin=admin)
    outcome = await make_outcome(nested_session, event_id=event1.id, label="Outcome 1")

    service = EventService(nested_session)
    with pytest.raises(OutcomeNotForEventError) as exc_info:
        await service.update_outcome(
            outcome_id=outcome.id, event_id=event2.id, by_admin_id=admin.id, label="New Label"
        )

    assert exc_info.value.event_id == event2.id
    assert exc_info.value.outcome_id == outcome.id


async def test_delete_outcome_with_correct_event_id_succeeds(
    nested_session: AsyncSession,
) -> None:
    """delete_outcome с правильным event_id успешно удаляет исход."""
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event = await make_event(nested_session, category=category, admin=admin)
    outcome = await make_outcome(nested_session, event_id=event.id, label="ToDelete")

    service = EventService(nested_session)
    await service.delete_outcome(outcome_id=outcome.id, event_id=event.id, by_admin_id=admin.id)

    await nested_session.flush()
    deleted = await service._outcomes.get_by_id(outcome.id)
    assert deleted is None


async def test_delete_outcome_with_wrong_event_id_raises(
    nested_session: AsyncSession,
) -> None:
    """delete_outcome с чужим event_id поднимает OutcomeNotForEventError."""
    from src.shared.exceptions import OutcomeNotForEventError

    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event1 = await make_event(nested_session, category=category, admin=admin)
    event2 = await make_event(nested_session, category=category, admin=admin)
    outcome = await make_outcome(nested_session, event_id=event1.id, label="Outcome 1")

    service = EventService(nested_session)
    with pytest.raises(OutcomeNotForEventError) as exc_info:
        await service.delete_outcome(outcome_id=outcome.id, event_id=event2.id, by_admin_id=admin.id)

    assert exc_info.value.event_id == event2.id
    assert exc_info.value.outcome_id == outcome.id
