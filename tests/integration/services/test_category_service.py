"""Integration-тесты `CategoryService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.services import CategoryService
from tests.integration.conftest import make_category

pytestmark = pytest.mark.integration


async def test_list_active_returns_only_active_sorted(
    nested_session: AsyncSession,
) -> None:
    a = await make_category(nested_session, sort_order=2, is_active=True)
    b = await make_category(nested_session, sort_order=1, is_active=True)
    _inactive = await make_category(nested_session, is_active=False)

    service = CategoryService(nested_session)
    cats = await service.list_active()
    ids = [c.id for c in cats]
    assert b.id in ids and a.id in ids
    assert _inactive.id not in ids
    # b (sort_order=1) идёт раньше a (sort_order=2)
    assert ids.index(b.id) < ids.index(a.id)


async def test_get_by_id_returns_none_for_missing(
    nested_session: AsyncSession,
) -> None:
    service = CategoryService(nested_session)
    assert await service.get_by_id(999_999) is None


async def test_get_by_slug_returns_correct(nested_session: AsyncSession) -> None:
    cat = await make_category(nested_session, slug="custom-football")
    service = CategoryService(nested_session)
    found = await service.get_by_slug("custom-football")
    assert found is not None
    assert found.id == cat.id
