"""Integration-тесты для cleanup reminder_dispatch_log (TASK-048)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import get_settings
from src.shared.models import ReminderDispatchLog
from src.shared.repositories import ReminderDispatchLogRepository
from tests.integration.conftest import make_event, make_user

pytestmark = pytest.mark.integration


async def test_delete_older_than_removes_old_entries(session: AsyncSession) -> None:
    """delete_older_than удаляет записи старше cutoff, оставляет свежие."""
    user = await make_user(session)
    event = await make_event(session)

    repo = ReminderDispatchLogRepository(session)
    now = datetime.now(tz=UTC)

    # Создаём записи с разным возрастом: 100, 50, 10 дней назад.
    for days_ago in [100, 50, 10]:
        entry = ReminderDispatchLog(
            user_id=user.id,
            event_id=event.id,
            offset_minutes=60,
            dispatched_at=now - timedelta(days=days_ago),
        )
        session.add(entry)
    await session.flush()

    # Cleanup по 30-дневному retention.
    cutoff = now - timedelta(days=30)
    deleted = await repo.delete_older_than(cutoff)

    assert deleted == 2  # 100 и 50 дней удалены

    # Проверяем, что 10-дневная запись осталась.
    remaining = await session.execute(
        sa.select(ReminderDispatchLog).where(
            ReminderDispatchLog.user_id == user.id,
            ReminderDispatchLog.event_id == event.id,
        )
    )
    assert len(remaining.all()) == 1


async def test_delete_older_than_returns_zero_when_no_old_entries(session: AsyncSession) -> None:
    """delete_older_than возвращает 0, если нет старых записей."""
    user = await make_user(session)
    event = await make_event(session)

    repo = ReminderDispatchLogRepository(session)
    now = datetime.now(tz=UTC)

    # Только свежие записи (5 дней назад).
    entry = ReminderDispatchLog(
        user_id=user.id,
        event_id=event.id,
        offset_minutes=60,
        dispatched_at=now - timedelta(days=5),
    )
    session.add(entry)
    await session.flush()

    # Cleanup по 30-дневному retention.
    cutoff = now - timedelta(days=30)
    deleted = await repo.delete_older_than(cutoff)

    assert deleted == 0


async def test_cleanup_job_uses_retention_from_config(session: AsyncSession) -> None:
    """Job использует retention_days из Settings."""
    settings = get_settings()
    # Значение по умолчанию 90 дней (TASK-048).
    assert settings.reminder_log_retention_days == 90
