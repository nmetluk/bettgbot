"""Integration-тесты `ReminderSettingRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.repositories import ReminderSettingRepository
from tests.integration.conftest import make_user

pytestmark = pytest.mark.integration


async def test_upsert_insert_then_update(session: AsyncSession) -> None:
    user = await make_user(session)
    repo = ReminderSettingRepository(session)
    rs = await repo.upsert(user_id=user.id, enabled=True, offsets_minutes=[1440, 60])
    assert rs.user_id == user.id
    assert rs.offsets_minutes == [1440, 60]
    assert rs.enabled is True

    rs2 = await repo.upsert(user_id=user.id, enabled=False, offsets_minutes=[5])
    assert rs2.user_id == user.id
    assert rs2.enabled is False
    assert rs2.offsets_minutes == [5]


async def test_list_eligible_user_ids(session: AsyncSession) -> None:
    u1 = await make_user(session)
    u2 = await make_user(session)
    u_disabled = await make_user(session)
    repo = ReminderSettingRepository(session)
    await repo.upsert(user_id=u1.id, enabled=True, offsets_minutes=[60, 1440])
    await repo.upsert(user_id=u2.id, enabled=True, offsets_minutes=[1440])
    await repo.upsert(user_id=u_disabled.id, enabled=False, offsets_minutes=[60])

    eligible_60 = await repo.list_eligible_user_ids(offset_minutes=60)
    assert u1.id in eligible_60
    assert u2.id not in eligible_60
    assert u_disabled.id not in eligible_60

    eligible_1440 = await repo.list_eligible_user_ids(offset_minutes=1440)
    assert u1.id in eligible_1440
    assert u2.id in eligible_1440
