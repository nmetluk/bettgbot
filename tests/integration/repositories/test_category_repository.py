"""Integration-тесты `CategoryRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import CategoryRepository
from tests.integration.conftest import make_category, make_event

pytestmark = pytest.mark.integration


async def test_create_and_get_by_slug(session: AsyncSession) -> None:
    repo = CategoryRepository(session)
    cat = await repo.create(name="Football", slug="football", sort_order=10)
    fetched = await repo.get_by_slug("football")
    assert fetched is not None
    assert fetched.id == cat.id
    assert fetched.sort_order == 10


async def test_list_active_only(session: AsyncSession) -> None:
    repo = CategoryRepository(session)
    active = await make_category(session, is_active=True)
    await make_category(session, is_active=False)

    all_ = await repo.list()
    only_active = await repo.list(active_only=True)
    assert {c.id for c in only_active} <= {c.id for c in all_}
    assert all(c.is_active for c in only_active)
    assert active.id in {c.id for c in only_active}


async def test_update_changes_fields(session: AsyncSession) -> None:
    cat = await make_category(session)
    repo = CategoryRepository(session)
    await repo.update(cat.id, name="Renamed", sort_order=99)
    await session.refresh(cat)
    assert cat.name == "Renamed"
    assert cat.sort_order == 99


async def test_delete_empty_category(session: AsyncSession) -> None:
    cat = await make_category(session)
    repo = CategoryRepository(session)
    await repo.delete(cat.id)
    assert await repo.get_by_id(cat.id) is None


async def test_delete_with_event_raises(session: AsyncSession) -> None:
    cat = await make_category(session)
    await make_event(session, category=cat)
    repo = CategoryRepository(session)
    with pytest.raises(IntegrityError):
        await repo.delete(cat.id)
        await session.flush()
