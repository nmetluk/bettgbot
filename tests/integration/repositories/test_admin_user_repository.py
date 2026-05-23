"""Integration-тесты `AdminUserRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import AdminUserRepository

pytestmark = pytest.mark.integration


async def test_create_and_get_by_login(session: AsyncSession) -> None:
    repo = AdminUserRepository(session)
    admin = await repo.create(login="alice-admin", password_hash="bcrypt-hash", full_name="Alice")
    fetched = await repo.get_by_login("alice-admin")
    assert fetched is not None
    assert fetched.id == admin.id
    assert fetched.full_name == "Alice"


async def test_unique_login(session: AsyncSession) -> None:
    repo = AdminUserRepository(session)
    await repo.create(login="bob", password_hash="h", full_name=None)
    with pytest.raises(IntegrityError):
        await repo.create(login="bob", password_hash="h2", full_name=None)


async def test_touch_last_login(session: AsyncSession) -> None:
    repo = AdminUserRepository(session)
    admin = await repo.create(login="carol", password_hash="h", full_name=None)
    assert admin.last_login_at is None
    await repo.touch_last_login(admin.id)
    await session.refresh(admin)
    assert admin.last_login_at is not None
