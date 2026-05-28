"""Integration-тесты для TASK-049: misfire catchup + расширенное окно.

Тесты проверяют:
- Расширенное окно (10 минут) корректно захватывает кандидатов в safety margin.
- Идемпотентность: второй прогон с тем же now не отправляет дубликаты.
- Симуляция misfire: два последовательных вызова dispatch_reminders корректны.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.scheduler.jobs import dispatch_reminders
from src.shared.models import Prediction
from src.shared.repositories import ReminderDispatchLogRepository
from src.shared.services import ReminderService
from tests.integration.conftest import make_admin, make_category, make_event, make_user

# nested_session fixture для сервис-тестов (commit внутри теста)
pytest_plugins = ["tests.integration.services.conftest"]

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
    from src.shared.models import ReminderSetting

    session.add(
        ReminderSetting(
            user_id=user_id,
            enabled=enabled,
            offsets_minutes=offsets,
        )
    )
    await session.flush()


def _make_session_maker(session: AsyncSession) -> MagicMock:
    """Возвращает session_maker, который из `async with` отдаёт `session`."""

    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


async def test_wider_window_catches_candidates_in_safety_margin(
    nested_session: AsyncSession,
) -> None:
    """TASK-049: окно 10 минут захватывает события в safety margin.

    Сценарий:
    - reminder offset = 60 минут
    - событие через 67 минут (offset + 7 минут запаса)
    - окно [60, 70) должно захватить это событие
    """
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=67)
    )
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.user_id == user.id
    assert cand.event_id == event.id
    assert cand.offset_minutes == 60


async def test_second_run_with_same_now_skips_already_recorded(
    nested_session: AsyncSession,
) -> None:
    """TASK-049: идемпотентность — второй вызов с тем же now не шлёт дубликаты.

    Сценарий:
    - Первый find_candidates возвращает кандидата.
    - record() успешно записывает (возвращает True).
    - Второй find_candidates (новая сессия, тот же now) видит dispatch_log и не возвращает кандидата.
    """
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=62))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    service = ReminderService(nested_session)
    dispatch_log = ReminderDispatchLogRepository(nested_session)

    # Первый тик: кандидат есть, запись успешна.
    candidates_first = await service.find_candidates(now=now, window_minutes=10)
    assert len(candidates_first) == 1

    recorded = await dispatch_log.record(
        user_id=candidates_first[0].user_id,
        event_id=candidates_first[0].event_id,
        offset_minutes=candidates_first[0].offset_minutes,
    )
    await nested_session.commit()
    assert recorded is True

    # Второй тик с тем же now: кандидат не должен вернуться (dispatch_log блокирует).
    candidates_second = await service.find_candidates(now=now, window_minutes=10)
    assert candidates_second == []


async def test_misfire_simulation_two_consecutive_dispatches(
    nested_session: AsyncSession,
) -> None:
    """TASK-049: симуляция misfire — два вызова dispatch_reminders подряд.

    Сценарий:
    - Scheduler пропустил тик, контейнер перезапустился.
    - APScheduler выполняет catch-up: dispatch_reminders для пропущенного тика.
    - Сразу же следующий тик (regular).
    - Кандидат должен быть отправлен ровно один раз.
    """
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=62))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    # Catch-up тик (misfire).
    await dispatch_reminders(
        bot=bot, session_maker=_make_session_maker(nested_session), window_minutes=10
    )

    # Regular тик сразу после (тот же now — симуляция быстрого catch-up).
    await dispatch_reminders(
        bot=bot, session_maker=_make_session_maker(nested_session), window_minutes=10
    )

    # Сообщение отправлено ровно один раз.
    assert bot.send_message.await_count == 1
    call_args = bot.send_message.call_args
    assert call_args[0][0] == user.tg_user_id


async def test_window_boundary_upper_exclusive(
    nested_session: AsyncSession,
) -> None:
    """TASK-049: верхняя граница окна эксклюзивна.

    Окно [60, 70) — событие ровно на 70 минут не попадает.
    """
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    await _make_published_event(nested_session, predictions_close_at=now + timedelta(minutes=70))
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert candidates == []


async def test_window_boundary_lower_inclusive(
    nested_session: AsyncSession,
) -> None:
    """TASK-049: нижняя граница окна инклюзивна.

    Окно [60, 70) — событие ровно на 60 минут попадает.
    """
    now = datetime.now(tz=UTC)
    user = await make_user(nested_session)
    event = await _make_published_event(
        nested_session, predictions_close_at=now + timedelta(minutes=60)
    )
    await _set_reminder(nested_session, user_id=user.id, offsets=[60])

    candidates = await ReminderService(nested_session).find_candidates(now=now, window_minutes=10)

    assert len(candidates) == 1
    assert candidates[0].event_id == event.id
