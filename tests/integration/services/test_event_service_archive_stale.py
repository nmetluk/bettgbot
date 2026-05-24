"""Integration-тесты `EventService.archive_stale_events` (TASK-018).

Покрывают «страховочный» путь архивации: события, у которых админ забыл
зафиксировать итог, через `threshold_days` дней должны помечаться
`is_archived=True` без `result_outcome_id`. Опирается на расширенный
CHECK `ck_event_result_archive_consistency` из миграции `0003`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.services import EventService
from tests.integration.conftest import (
    make_admin,
    make_category,
    make_event,
    make_outcome,
)

pytestmark = pytest.mark.integration


async def test_archive_stale_events_archives_old_unresolved_event(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    starts_at = now - timedelta(days=10)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(minutes=10),
        is_published=True,
        is_archived=False,
    )

    count = await EventService(nested_session).archive_stale_events(now=now)

    assert count == 1
    await nested_session.refresh(event)
    assert event.is_archived is True
    assert event.archived_at is not None
    assert event.result_outcome_id is None


async def test_archive_stale_events_skips_recent_event(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    starts_at = now - timedelta(days=3)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(minutes=10),
        is_published=True,
        is_archived=False,
    )

    count = await EventService(nested_session).archive_stale_events(now=now)

    assert count == 0
    await nested_session.refresh(event)
    assert event.is_archived is False


async def test_archive_stale_events_skips_resolved_event(
    nested_session: AsyncSession,
) -> None:
    # Нормальный путь архивации через set_result: result_outcome_id + is_archived.
    now = datetime.now(tz=UTC)
    starts_at = now - timedelta(days=10)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(minutes=10),
        is_published=True,
    )
    outcome = await make_outcome(nested_session, event_id=event.id)
    event.result_outcome_id = outcome.id
    event.is_archived = True
    event.archived_at = starts_at + timedelta(hours=1)
    archived_before = event.archived_at
    await nested_session.flush()

    count = await EventService(nested_session).archive_stale_events(now=now)

    assert count == 0
    await nested_session.refresh(event)
    assert event.archived_at == archived_before


async def test_archive_stale_events_skips_already_archived(
    nested_session: AsyncSession,
) -> None:
    # is_archived=True уже стоит — повторно update'ить не нужно.
    # После 0003 CHECK разрешает «архивный без result» — но при is_archived=true
    # job-фильтр исключает такие события (Event.is_archived.is_(False)).
    now = datetime.now(tz=UTC)
    starts_at = now - timedelta(days=10)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(minutes=10),
        is_published=True,
        is_archived=True,
        archived_at=now - timedelta(days=5),
    )

    count = await EventService(nested_session).archive_stale_events(now=now)

    assert count == 0
    await nested_session.refresh(event)
    assert event.result_outcome_id is None
    assert event.is_archived is True


async def test_archive_stale_events_custom_threshold(
    nested_session: AsyncSession,
) -> None:
    # threshold_days=2 → событие 3 дня назад уже стейл.
    now = datetime.now(tz=UTC)
    starts_at = now - timedelta(days=3)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(minutes=10),
        is_published=True,
        is_archived=False,
    )

    count = await EventService(nested_session).archive_stale_events(now=now, threshold_days=2)

    assert count == 1
    await nested_session.refresh(event)
    assert event.is_archived is True
    assert event.archived_at is not None
