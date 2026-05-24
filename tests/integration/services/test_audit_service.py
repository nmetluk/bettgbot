"""Integration-тесты `AuditService`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.services import AuditService
from tests.integration.conftest import make_admin

pytestmark = pytest.mark.integration


async def test_add_returns_with_id_no_commit(nested_session: AsyncSession) -> None:
    admin = await make_admin(nested_session)
    service = AuditService(nested_session)
    entry = await service.add(admin_id=admin.id, action="category.create", payload={"name": "X"})
    assert entry.id is not None
    assert entry.action == "category.create"


async def test_list_and_count_filters(nested_session: AsyncSession) -> None:
    a1 = await make_admin(nested_session)
    a2 = await make_admin(nested_session)
    service = AuditService(nested_session)
    await service.add(admin_id=a1.id, action="event.publish", payload={})
    await service.add(admin_id=a1.id, action="event.update", payload={})
    await service.add(admin_id=a2.id, action="event.publish", payload={})

    by_a1 = await service.list(admin_id=a1.id)
    assert all(e.admin_id == a1.id for e in by_a1)

    publishes = await service.list(action="event.publish")
    assert all(e.action == "event.publish" for e in publishes)

    assert await service.count(admin_id=a1.id) == 2
    assert await service.count(action="event.publish") == 2


async def test_list_window(nested_session: AsyncSession) -> None:
    admin = await make_admin(nested_session)
    service = AuditService(nested_session)
    await service.add(admin_id=admin.id, action="x", payload={})

    now = datetime.now(tz=UTC)
    found = await service.list(since=now - timedelta(hours=1), until=now + timedelta(hours=1))
    assert any(e.admin_id == admin.id for e in found)


async def test_list_eager_loads_admin(nested_session: AsyncSession) -> None:
    """`selectinload(AuditLog.admin)` подгружает admin без отдельного SELECT (TASK-026 Step 0)."""
    admin = await make_admin(nested_session, full_name="Test Admin", login="eager-test")
    service = AuditService(nested_session)
    await service.add(admin_id=admin.id, action="eager.check", payload={"k": "v"})
    await nested_session.commit()

    entries = await service.list(admin_id=admin.id, action="eager.check")
    assert len(entries) >= 1
    entry = entries[0]
    # Доступ к admin не должен дёргать lazy IO — selectinload загрузил.
    assert entry.admin.login == "eager-test"
    assert entry.admin.full_name == "Test Admin"
