"""Conftest для scheduler integration-тестов (TASK-061-amendment)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def clean_session(session: AsyncSession) -> AsyncSession:
    """Очищает User и Broadcast таблицы перед тестом."""
    from src.shared.models import Broadcast, User

    # Удаляем все записи
    for b in (await session.execute(select(Broadcast))).scalars().all():
        await session.delete(b)
    for u in (await session.execute(select(User))).scalars().all():
        await session.delete(u)
    await session.flush()

    yield session
