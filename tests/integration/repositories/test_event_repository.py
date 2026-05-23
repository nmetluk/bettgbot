"""Integration-тесты `EventRepository`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import EventRepository
from tests.integration.conftest import (
    make_admin,
    make_category,
    make_event,
    make_outcome,
)

pytestmark = pytest.mark.integration


async def test_create_and_get_by_id(session: AsyncSession) -> None:
    category = await make_category(session)
    admin = await make_admin(session)
    repo = EventRepository(session)
    starts = datetime.now(tz=UTC) + timedelta(days=1)
    event = await repo.create(
        category_id=category.id,
        title="Test match",
        description="desc",
        metadata={"league": "X"},
        starts_at=starts,
        predictions_close_at=starts - timedelta(minutes=15),
        created_by_admin_id=admin.id,
    )
    fetched = await repo.get_by_id(event.id)
    assert fetched is not None
    assert fetched.title == "Test match"
    assert fetched.metadata_ == {"league": "X"}


async def test_get_with_outcomes_eager_loads(session: AsyncSession) -> None:
    event = await make_event(session)
    await make_outcome(session, event.id, label="A")
    await make_outcome(session, event.id, label="B")
    repo = EventRepository(session)
    fetched = await repo.get_with_outcomes(event.id)
    assert fetched is not None
    labels = {o.label for o in fetched.outcomes}
    assert labels == {"A", "B"}


async def test_list_active_filters_published_and_unarchived(
    session: AsyncSession,
) -> None:
    published = await make_event(session, is_published=True, is_archived=False)
    await make_event(session, is_published=False)  # draft

    repo = EventRepository(session)
    active = await repo.list_active()
    ids = {e.id for e in active}
    assert published.id in ids


async def test_list_for_admin_status_draft(session: AsyncSession) -> None:
    await make_event(session, is_published=False)
    await make_event(session, is_published=True)
    repo = EventRepository(session)
    drafts = await repo.list_for_admin(status="draft")
    assert all(e.is_published is False and e.is_archived is False for e in drafts)


async def test_set_result_updates_fields(session: AsyncSession) -> None:
    event = await make_event(session)
    outcome = await make_outcome(session, event.id, label="winner")
    repo = EventRepository(session)
    archived_at = datetime.now(tz=UTC)
    await repo.set_result(event.id, outcome.id, archived_at)
    await session.refresh(event)
    assert event.result_outcome_id == outcome.id
    assert event.is_archived is True
    assert event.archived_at is not None


async def test_list_with_deadline_in_window(session: AsyncSession) -> None:
    now = datetime.now(tz=UTC)
    inside = await make_event(
        session,
        is_published=True,
        is_archived=False,
        predictions_close_at=now + timedelta(minutes=30),
        starts_at=now + timedelta(hours=2),
    )
    await make_event(
        session,
        is_published=True,
        is_archived=False,
        predictions_close_at=now + timedelta(hours=5),
        starts_at=now + timedelta(hours=6),
    )
    repo = EventRepository(session)
    found = await repo.list_with_deadline_in_window(since=now, until=now + timedelta(hours=1))
    ids = {e.id for e in found}
    assert inside.id in ids
