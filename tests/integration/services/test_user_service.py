"""Integration-тесты `UserService`."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import AuditLog, ReminderSetting
from src.shared.services import UserService

pytestmark = pytest.mark.integration


async def test_register_creates_user_with_default_reminders(
    nested_session: AsyncSession,
) -> None:
    """Открытая регистрация (TASK-096): создаёт User + дефолтные напоминания без реестра."""
    service = UserService(nested_session)
    user = await service.register_or_authenticate(tg_user_id=111, phone="+71", first_name="Alice")
    assert user.id is not None

    rs = (
        await nested_session.execute(
            select(ReminderSetting).where(ReminderSetting.user_id == user.id)
        )
    ).scalar_one()
    assert rs.enabled is True
    assert rs.offsets_minutes == [1440, 60]


async def test_register_existing_updates_last_seen(
    nested_session: AsyncSession,
) -> None:
    """Повторная регистрация того же tg_user_id → touch last_seen, без дубликата."""
    service = UserService(nested_session)
    user = await service.register_or_authenticate(tg_user_id=555, phone="+75", first_name="Eve")
    initial = user.last_seen_at

    again = await service.register_or_authenticate(tg_user_id=555, phone="+75", first_name="Eve")
    await nested_session.refresh(again)
    assert again.id == user.id
    assert again.last_seen_at >= initial


async def test_block_writes_audit(
    nested_session: AsyncSession,
) -> None:
    from tests.integration.conftest import make_admin, make_user

    admin = await make_admin(nested_session)
    user = await make_user(nested_session)
    service = UserService(nested_session)

    await service.block(user.id, admin.id)
    await nested_session.refresh(user)
    assert user.is_blocked is True

    entry = (
        await nested_session.execute(
            select(AuditLog)
            .where(AuditLog.action == "user.block", AuditLog.admin_id == admin.id)
            .order_by(AuditLog.id.desc())
        )
    ).scalar_one_or_none()
    assert entry is not None
    assert entry.payload == {"user_id": user.id}


async def test_unblock_writes_audit(
    nested_session: AsyncSession,
) -> None:
    from tests.integration.conftest import make_admin, make_user

    admin = await make_admin(nested_session)
    user = await make_user(nested_session, is_blocked=True)
    service = UserService(nested_session)

    await service.unblock(user.id, admin.id)
    await nested_session.refresh(user)
    assert user.is_blocked is False
