"""Conftest для scheduler integration-тестов (TASK-061-amendment)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def clean_session(session: AsyncSession) -> AsyncSession:
    """Очищает Broadcast таблицы перед и после теста.

    Используется для dispatch_broadcasts тестов, которые делают commit.
    cleanup в teardown гарантирует, что последующие тесты не видят эти данные.

    NOTA BENE: Не удаляет Users, т.к. есть FK constraints из других таблиц.
    Dispatch тесты создают пользователей через make_user, и они остаются в БД,
    но это не должно влиять на другие тесты, которые делают proper rollback.
    """
    from src.shared.models import Broadcast, BroadcastDelivery

    # Cleanup перед тестом
    await session.execute(delete(BroadcastDelivery))
    await session.execute(delete(Broadcast))
    await session.commit()

    yield session

    # Cleanup после теста
    await session.execute(delete(BroadcastDelivery))
    await session.execute(delete(Broadcast))
    await session.commit()
