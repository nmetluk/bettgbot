"""Integration-тесты `AdminAuthService` (TASK-020)."""

from __future__ import annotations

import bcrypt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import AdminInactiveError, AdminInvalidCredentialsError
from src.shared.models import AdminUser
from src.shared.services import AdminAuthService

pytestmark = pytest.mark.integration


async def _make_admin(
    session: AsyncSession,
    *,
    login: str,
    password: str,
    is_active: bool = True,
) -> AdminUser:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode(
        "ascii"
    )
    admin = AdminUser(
        login=login,
        password_hash=password_hash,
        full_name=None,
        is_active=is_active,
    )
    session.add(admin)
    await session.flush()
    return admin


async def test_authenticate_success_updates_last_login_at(
    nested_session: AsyncSession,
) -> None:
    admin = await _make_admin(nested_session, login="alice-int", password="hunter2")
    assert admin.last_login_at is None

    result = await AdminAuthService(nested_session).authenticate(
        login="alice-int", password="hunter2"
    )

    assert result.id == admin.id
    await nested_session.refresh(admin)
    assert admin.last_login_at is not None


async def test_authenticate_wrong_password_raises_invalid_credentials(
    nested_session: AsyncSession,
) -> None:
    await _make_admin(nested_session, login="bob-int", password="correct")
    with pytest.raises(AdminInvalidCredentialsError):
        await AdminAuthService(nested_session).authenticate(login="bob-int", password="wrong")


async def test_authenticate_unknown_login_raises_invalid_credentials(
    nested_session: AsyncSession,
) -> None:
    # Анти-enumeration: для неизвестного login — тот же exception, что для wrong password.
    with pytest.raises(AdminInvalidCredentialsError):
        await AdminAuthService(nested_session).authenticate(
            login="no-such-admin-int", password="anything"
        )


async def test_authenticate_inactive_admin_raises_inactive(
    nested_session: AsyncSession,
) -> None:
    admin = await _make_admin(nested_session, login="dave-int", password="ok", is_active=False)
    with pytest.raises(AdminInactiveError) as exc_info:
        await AdminAuthService(nested_session).authenticate(login="dave-int", password="ok")
    assert exc_info.value.admin_id == admin.id
