"""Integration-тесты `ReminderService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.exceptions import InvalidReminderOffsetsError
from src.shared.services import ReminderService
from tests.integration.conftest import make_user

pytestmark = pytest.mark.integration


async def test_update_happy_sorts_desc(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = ReminderService(nested_session)
    rs = await service.update(user_id=user.id, enabled=True, offsets_minutes=[60, 1440, 30])
    assert rs.offsets_minutes == [1440, 60, 30]
    assert rs.enabled is True


async def test_update_too_many_offsets(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = ReminderService(nested_session)
    with pytest.raises(InvalidReminderOffsetsError):
        await service.update(user_id=user.id, enabled=True, offsets_minutes=[5, 10, 15, 20, 25, 30])


async def test_update_offset_below_minimum(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = ReminderService(nested_session)
    with pytest.raises(InvalidReminderOffsetsError):
        await service.update(user_id=user.id, enabled=True, offsets_minutes=[4])


async def test_update_duplicates(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = ReminderService(nested_session)
    with pytest.raises(InvalidReminderOffsetsError):
        await service.update(user_id=user.id, enabled=True, offsets_minutes=[60, 60])
