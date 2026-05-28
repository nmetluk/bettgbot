"""Integration-тесты `ReminderService.find_candidates` (TASK-017).

Все сценарии работают с реальным PostgreSQL через `nested_session`-фикстуру.
Параметр `now` передаём в `find_candidates` явно, чтобы окно событий
не зависело от системного времени.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import (
    Prediction,
    ReminderDispatchLog,
    ReminderSetting,
)
from src.shared.services import ReminderService
from tests.integration.conftest import (
    make_admin,
    make_category,
    make_event,
    make_outcome,
    make_user,
)

pytestmark = pytest.mark.integration


async def _make_published_event(
    session: AsyncSession,
    *,
    predictions_close_at: datetime,
):
    """Опубликованное, неархивное событие с заданным `predictions_close_at`."""
    category = await make_category(session)
    admin = await make_admin(session)
    return await make_event(
        session,
        category=category,
        admin=admin,
        is_published=True,
        is_archived=False,
        starts_at=predictions_close_at + timedelta(minutes=30),
        predictions_close_at=predictions_close_at,
    )


async def _set_reminder(
    session: AsyncSession, *, user_id: int, offsets: list[int], enabled: bool = True
) -> None:
    session.add(
        ReminderSetting(
            user_id=user_id,
            enabled=enabled,
            offsets_minutes=offsets,
        )
    )
    await session.flush()


async def test_find_candidates_user_with_matching_offset_returns_candidate(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=62)
    )
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.user_id == user.id
    assert cand.tg_user_id == user.tg_user_id
    assert cand.event_id == event.id
    assert cand.event_title == event.title
    assert cand.offset_minutes == 60


async def test_find_candidates_disabled_setting_excluded(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=62))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60], enabled=False)

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []


async def test_find_candidates_offset_outside_window_excluded(
    nested_session: AsyncSession,
) -> None:
    # offset=60, window=[60, 70); событие до дедлайна за 70 минут → не попадает (верхняя граница эксклюзивна).
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=70))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert candidates == []


async def test_find_candidates_with_prediction_excluded(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=62)
    )
    outcome = await make_outcome(nested_session, event_id=event.id)
    nested_session.add(Prediction(user_id=user.id, event_id=event.id, outcome_id=outcome.id))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []


async def test_find_candidates_already_dispatched_excluded(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=62)
    )
    nested_session.add(ReminderDispatchLog(user_id=user.id, event_id=event.id, offset_minutes=60))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []


async def test_find_candidates_archived_event_excluded(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=62)
    )
    # Архивируем (учитываем CHECK ck_event_result_archive_consistency:
    # archive ⇒ есть result_outcome_id + archived_at).
    outcome = await make_outcome(nested_session, event_id=event.id)
    event.result_outcome_id = outcome.id
    event.is_archived = True
    event.archived_at = now
    await nested_session.flush()
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []


async def test_find_candidates_unpublished_event_excluded(
    nested_session: AsyncSession,
) -> None:
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    category = await make_category(nested_session)
    admin = await make_admin(nested_session)
    await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=False,
        is_archived=False,
        starts_at=now + timedelta(minutes=92),
        predictions_close_at=now + timedelta(minutes=62),
    )
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []


async def test_find_candidates_multiple_offsets_returns_only_matching(
    nested_session: AsyncSession,
) -> None:
    # Юзер ждёт за 60 мин и за сутки. Событие — за 62 мин до дедлайна.
    # Должен вернуться только offset=60.
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=62))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60, 1440])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert len(candidates) == 1
    assert candidates[0].offset_minutes == 60


async def test_find_candidates_blocked_user_excluded(
    nested_session: AsyncSession,
) -> None:
    # Дополнительный сценарий: заблокированному админом юзеру не шлём напоминания.
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session, is_blocked=True)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=62))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now)

    assert candidates == []
