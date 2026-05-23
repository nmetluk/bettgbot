"""Integration-тесты `AuditLogRepository`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import AuditLogRepository
from tests.integration.conftest import make_admin

pytestmark = pytest.mark.integration


async def test_add_returns_with_id(session: AsyncSession) -> None:
    admin = await make_admin(session)
    repo = AuditLogRepository(session)
    entry = await repo.add(
        admin_id=admin.id, action="category.create", payload={"name": "Football"}
    )
    assert entry.id is not None
    assert entry.action == "category.create"
    assert entry.payload == {"name": "Football"}


async def test_list_and_count_with_filters(session: AsyncSession) -> None:
    admin1 = await make_admin(session)
    admin2 = await make_admin(session)
    repo = AuditLogRepository(session)
    await repo.add(admin_id=admin1.id, action="category.create", payload={})
    await repo.add(admin_id=admin1.id, action="event.publish", payload={})
    await repo.add(admin_id=admin2.id, action="category.create", payload={})

    all_admin1 = await repo.list(admin_id=admin1.id)
    assert len(all_admin1) == 2
    assert all(e.admin_id == admin1.id for e in all_admin1)

    only_creates = await repo.list(action="category.create")
    assert all(e.action == "category.create" for e in only_creates)

    assert await repo.count(admin_id=admin1.id) == 2
    assert await repo.count(action="event.publish") == 1


async def test_list_window(session: AsyncSession) -> None:
    admin = await make_admin(session)
    repo = AuditLogRepository(session)
    await repo.add(admin_id=admin.id, action="x", payload={})

    now = datetime.now(tz=UTC)
    found = await repo.list(since=now - timedelta(hours=1), until=now + timedelta(hours=1))
    assert any(e.admin_id == admin.id for e in found)
    assert (await repo.count(since=now - timedelta(hours=1), until=now + timedelta(hours=1))) >= 1
