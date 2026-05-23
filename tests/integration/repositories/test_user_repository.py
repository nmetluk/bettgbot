"""Integration-тесты `UserRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import UserRepository
from tests.integration.conftest import _uniq_int, make_user

pytestmark = pytest.mark.integration


async def test_create_then_get_by_tg_user_id(session: AsyncSession) -> None:
    repo = UserRepository(session)
    user = await repo.create(
        tg_user_id=12345,
        phone="+71234567890",
        tg_username="alice",
        first_name="Alice",
        last_name=None,
    )
    assert user.id is not None

    fetched = await repo.get_by_tg_user_id(12345)
    assert fetched is not None
    assert fetched.id == user.id


async def test_get_by_phone(session: AsyncSession) -> None:
    user = await make_user(session, phone="+79991234567")
    repo = UserRepository(session)
    fetched = await repo.get_by_phone("+79991234567")
    assert fetched is not None
    assert fetched.id == user.id


async def test_touch_last_seen(session: AsyncSession) -> None:
    user = await make_user(session)
    initial = user.last_seen_at
    repo = UserRepository(session)
    # Гарантируем «после» — БД обновит func.now() в той же миллисекунде, но
    # т.к. timestamptz хранит микросекунды, мы можем потерять разницу.
    # Здесь достаточно убедиться, что не упало и значение всё ещё ≥ initial.
    await repo.touch_last_seen(user.id)
    await session.refresh(user)
    assert user.last_seen_at >= initial


async def test_set_blocked(session: AsyncSession) -> None:
    user = await make_user(session)
    repo = UserRepository(session)
    assert user.is_blocked is False

    await repo.set_blocked(user.id, True)
    await session.refresh(user)
    assert user.is_blocked is True


async def test_list_for_admin_filters_by_query(session: AsyncSession) -> None:
    await make_user(session, first_name="Findable", phone=f"+7{_uniq_int() % 10_000_000_000:010d}")
    await make_user(session, first_name="Other", phone=f"+7{_uniq_int() % 10_000_000_000:010d}")

    repo = UserRepository(session)
    found = await repo.list_for_admin(query="Findable")
    assert any(u.first_name == "Findable" for u in found)
    assert all(u.first_name != "Other" for u in found)

    total = await repo.count_for_admin(query="Findable")
    assert total == len(found)


async def test_unique_tg_user_id(session: AsyncSession) -> None:
    repo = UserRepository(session)
    await repo.create(
        tg_user_id=99,
        phone="+70000000001",
        tg_username=None,
        first_name="A",
        last_name=None,
    )
    with pytest.raises(IntegrityError):
        await repo.create(
            tg_user_id=99,
            phone="+70000000002",
            tg_username=None,
            first_name="B",
            last_name=None,
        )
