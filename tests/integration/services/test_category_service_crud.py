"""Integration-тесты `CategoryService` CRUD (TASK-021)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import (
    CategoryHasEventsError,
    CategoryNotFoundError,
    CategorySlugConflictError,
)
from src.shared.models import AuditLog
from src.shared.services import CategoryService
from tests.integration.conftest import make_admin, make_category, make_event

pytestmark = pytest.mark.integration


async def test_create_category_writes_audit_and_returns_category(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    service = CategoryService(nested_session)

    category = await service.create_category(
        name="Футбол-int",
        slug="football-int-1",
        sort_order=10,
        is_active=True,
        by_admin_id=admin.id,
    )

    assert category.id is not None
    assert category.name == "Футбол-int"

    log_result = await nested_session.execute(
        select(AuditLog).where(AuditLog.action == "category.create")
    )
    logs = log_result.scalars().all()
    assert any(log.payload.get("category_id") == category.id for log in logs)


async def test_create_category_duplicate_slug_raises_conflict(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    await make_category(nested_session, slug="dup-slug-int")

    with pytest.raises(CategorySlugConflictError) as exc_info:
        await CategoryService(nested_session).create_category(
            name="X", slug="dup-slug-int", by_admin_id=admin.id
        )
    assert exc_info.value.slug == "dup-slug-int"


async def test_update_category_unknown_id_raises_not_found(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    with pytest.raises(CategoryNotFoundError) as exc_info:
        await CategoryService(nested_session).update_category(
            999999, by_admin_id=admin.id, name="X"
        )
    assert exc_info.value.category_id == 999999


async def test_update_category_writes_audit(nested_session: AsyncSession) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session, name="Old")
    service = CategoryService(nested_session)

    await service.update_category(category.id, by_admin_id=admin.id, name="New")

    await nested_session.refresh(category)
    assert category.name == "New"

    log_result = await nested_session.execute(
        select(AuditLog).where(AuditLog.action == "category.update")
    )
    logs = log_result.scalars().all()
    assert any(log.payload.get("category_id") == category.id for log in logs)


async def test_delete_category_empty_succeeds(nested_session: AsyncSession) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    service = CategoryService(nested_session)

    await service.delete_category(category.id, by_admin_id=admin.id)

    assert await service.get_by_id(category.id) is None


async def test_delete_category_with_events_raises_has_events(
    nested_session: AsyncSession,
) -> None:
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    await make_event(nested_session, category=category, admin=admin)

    with pytest.raises(CategoryHasEventsError) as exc_info:
        await CategoryService(nested_session).delete_category(category.id, by_admin_id=admin.id)
    assert exc_info.value.category_id == category.id


async def test_list_all_with_counts_returns_zero_for_empty_category(
    nested_session: AsyncSession,
) -> None:
    category = await make_category(nested_session, name="EmptyCat")
    rows = await CategoryService(nested_session).list_all_with_counts()
    # Ищем нашу категорию в результате.
    found = [(c, n) for (c, n) in rows if c.id == category.id]
    assert len(found) == 1
    assert found[0][1] == 0
