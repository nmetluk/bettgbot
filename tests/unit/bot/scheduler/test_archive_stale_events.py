"""Тесты `archive_stale_events` job (TASK-018)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.bot.scheduler.jobs import archive_stale_events


def _make_session_maker(session: MagicMock) -> MagicMock:
    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


@pytest.fixture
def session_mock() -> MagicMock:
    return MagicMock()


async def test_archive_stale_events_calls_service_and_logs_count(
    session_mock: MagicMock,
) -> None:
    service_instance = MagicMock()
    service_instance.archive_stale_events = AsyncMock(return_value=3)
    logger_mock = MagicMock()

    with (
        patch("src.bot.scheduler.jobs.EventService", return_value=service_instance),
        patch("src.bot.scheduler.jobs.logger", logger_mock),
    ):
        await archive_stale_events(session_maker=_make_session_maker(session_mock))

    service_instance.archive_stale_events.assert_awaited_once_with()
    logger_mock.info.assert_called_once_with("scheduler.archive_stale.done", archived_count=3)


async def test_archive_stale_events_handles_zero_archived(
    session_mock: MagicMock,
) -> None:
    # Лог обязателен и при count=0 — метрика «job отработал».
    service_instance = MagicMock()
    service_instance.archive_stale_events = AsyncMock(return_value=0)
    logger_mock = MagicMock()

    with (
        patch("src.bot.scheduler.jobs.EventService", return_value=service_instance),
        patch("src.bot.scheduler.jobs.logger", logger_mock),
    ):
        await archive_stale_events(session_maker=_make_session_maker(session_mock))

    logger_mock.info.assert_called_once_with("scheduler.archive_stale.done", archived_count=0)
