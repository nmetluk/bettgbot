"""Integration-тесты `UserService`."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import RegistryUnavailableError, UserNotAllowed
from src.shared.external.registry import ExternalApiError, VerificationResult
from src.shared.models import AuditLog, ReminderSetting
from src.shared.services import UserService
from tests.integration.services.conftest import StubRegistry

pytestmark = pytest.mark.integration


async def test_register_creates_user_with_default_reminders(
    nested_session: AsyncSession,
) -> None:
    registry = StubRegistry(result=VerificationResult(is_allowed=True, external_user_id="u-1"))
    service = UserService(nested_session, registry)
    user = await service.register_or_authenticate(tg_user_id=111, phone="+71", first_name="Alice")
    assert user.id is not None

    rs = (
        await nested_session.execute(
            select(ReminderSetting).where(ReminderSetting.user_id == user.id)
        )
    ).scalar_one()
    assert rs.enabled is True
    assert rs.offsets_minutes == [1440, 60]


async def test_register_not_found_raises_user_not_allowed(
    nested_session: AsyncSession,
) -> None:
    registry = StubRegistry(result=VerificationResult(is_allowed=False, reason="not_found"))
    service = UserService(nested_session, registry)
    with pytest.raises(UserNotAllowed) as exc:
        await service.register_or_authenticate(tg_user_id=222, phone="+72", first_name="Bob")
    assert exc.value.reason == "not_found"


async def test_register_blocked_raises_user_not_allowed(
    nested_session: AsyncSession,
) -> None:
    registry = StubRegistry(result=VerificationResult(is_allowed=False, reason="manual"))
    service = UserService(nested_session, registry)
    with pytest.raises(UserNotAllowed) as exc:
        await service.register_or_authenticate(tg_user_id=333, phone="+73", first_name="Carol")
    assert exc.value.reason == "manual"


async def test_register_external_api_error_wrapped(
    nested_session: AsyncSession,
) -> None:
    original = ExternalApiError("network down")
    registry = StubRegistry(raises=original)
    service = UserService(nested_session, registry)
    with pytest.raises(RegistryUnavailableError) as exc:
        await service.register_or_authenticate(tg_user_id=444, phone="+74", first_name="Dan")
    assert exc.value.__cause__ is original


async def test_register_existing_updates_last_seen(
    nested_session: AsyncSession,
) -> None:
    registry = StubRegistry(result=VerificationResult(is_allowed=True))
    service = UserService(nested_session, registry)
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
    registry = StubRegistry(result=VerificationResult(is_allowed=False))
    service = UserService(nested_session, registry)

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
    registry = StubRegistry(result=VerificationResult(is_allowed=False))
    service = UserService(nested_session, registry)

    await service.unblock(user.id, admin.id)
    await nested_session.refresh(user)
    assert user.is_blocked is False
