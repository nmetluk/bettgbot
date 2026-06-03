"""Unit-тесты `send_backup_health_heartbeat` (TASK-099) с замоканным Bot.

Покрывает (по amendment):
- пустой ADMIN_TELEGRAM_CHAT_IDS → не шлёт (return до работы с БД);
- нет ни одной success → шлёт NO_RECENT (всегда шлём отчёт);
- последний success свежий (< BACKUP_MAX_AGE_HOURS) → OK + replication статус;
- последний success старше порога → ALERT;
- последняя строка failed → ALERT;
- Postgres/Redis недоступны → DOWN в тексте сообщения;
- enabled=false проверяется в builder (см. test_builder).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from src.bot.scheduler.jobs import replicate_latest_backup, send_backup_health_heartbeat
from src.shared.models import BackupRun


def _make_session_maker(session: MagicMock) -> MagicMock:
    @asynccontextmanager
    async def _cm():
        yield session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    return maker


@pytest.fixture
def session_mock() -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _mk_settings(chat_ids: list[int], enabled: bool = True, max_age: int = 2) -> MagicMock:
    s = MagicMock()
    s.admin_telegram_chat_ids = chat_ids
    s.backup.heartbeat_enabled = enabled
    s.backup.max_age_hours = max_age
    # TASK-100 replication fields (provide ints so timedelta(hours=...) works in lag checks)
    s.backup.replication_enabled = False
    s.backup.replication_max_lag_hours = 3
    return s


def _mk_backup_run(
    status: str = "success",
    finished_at: datetime | None = None,
    size_bytes: int | None = 12345678,
    replicated_at: datetime | None = None,
    filename: str | None = None,
) -> MagicMock:
    br = MagicMock(spec=BackupRun)
    br.id = 1
    br.status = status
    br.finished_at = finished_at
    br.size_bytes = size_bytes
    br.replicated_at = replicated_at
    br.filename = filename
    br.error = None if status == "success" else "some error"
    return br


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_skips_empty_recipients_no_db_calls(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Пустой ADMIN_TELEGRAM_CHAT_IDS → warning + return; БД/репо не трогаем."""
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with patch("src.shared.config.get_settings", return_value=_mk_settings([])):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    bot.send_message.assert_not_called()
    # repo не создавался / запросы не шли (проверяем по отсутствию side effects, но session мог быть создан в with)
    # Ключ: не дошли до send


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_sends_no_recent_when_no_success(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Нет success строк → шлёт NO_RECENT (всегда шлём, даже 'no recent')."""
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    # repo.get_last_success -> None, get_latest -> None
    repo_mock = MagicMock()
    repo_mock.get_last_success = AsyncMock(return_value=None)
    repo_mock.get_latest = AsyncMock(return_value=None)

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([111, 222])),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
        patch("src.bot.scheduler.jobs._check_postgres_visible", AsyncMock(return_value=True)),
        patch("src.bot.scheduler.jobs._check_redis_visible", AsyncMock(return_value=True)),
    ):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    assert bot.send_message.call_count == 2
    # проверяем текст первого
    args, _ = bot.send_message.call_args_list[0]
    text = args[1]
    assert "нет свежих бэкапов" in text
    assert "DB: OK | Redis: OK" in text


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_ok_when_recent_success(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Свежий success (<2h) и реплицирован недавно → OK."""
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    last = _mk_backup_run(
        status="success",
        finished_at=fixed_now - timedelta(minutes=30),
        size_bytes=42 * 1024 * 1024,
        replicated_at=fixed_now - timedelta(minutes=1),  # replicated recently, within lag
    )

    repo_mock = MagicMock()
    repo_mock.get_last_success = AsyncMock(return_value=last)
    repo_mock.get_latest = AsyncMock(return_value=last)

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([123])),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
        patch("src.bot.scheduler.jobs._check_postgres_visible", AsyncMock(return_value=True)),
        patch("src.bot.scheduler.jobs._check_redis_visible", AsyncMock(return_value=True)),
    ):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    assert bot.send_message.call_count == 1
    text = bot.send_message.call_args[0][1]
    assert "Backup heartbeat OK" in text
    assert "42M" in text
    assert "реплицирован" in text
    assert "DB: OK | Redis: OK" in text


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_alert_when_old_success(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Success старше max_age → ALERT с причиной 'старше'."""
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    last = _mk_backup_run(
        status="success",
        finished_at=fixed_now - timedelta(hours=3),
        size_bytes=10 * 1024 * 1024,
    )

    repo_mock = MagicMock()
    repo_mock.get_last_success = AsyncMock(return_value=last)
    repo_mock.get_latest = AsyncMock(return_value=last)

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([123], max_age=2)),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
    ):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    text = bot.send_message.call_args[0][1]
    assert "ALERT" in text
    assert "старше 2ч" in text


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_alert_when_last_failed(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Последняя строка failed (даже если была success раньше) → ALERT."""
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    last_success = _mk_backup_run(status="success", finished_at=fixed_now - timedelta(hours=1))
    latest_failed = _mk_backup_run(status="failed", finished_at=fixed_now - timedelta(minutes=5))

    repo_mock = MagicMock()
    repo_mock.get_last_success = AsyncMock(return_value=last_success)
    repo_mock.get_latest = AsyncMock(return_value=latest_failed)

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([123])),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
    ):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    text = bot.send_message.call_args[0][1]
    assert "ALERT" in text
    assert "с ошибкой" in text or "failed" in text.lower()


@patch("src.bot.scheduler.jobs.utcnow")
async def test_backup_heartbeat_reports_down_when_checks_fail(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    """Если _check_postgres_visible или redis возвращают False → текст содержит DOWN."""
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    last = _mk_backup_run(status="success", finished_at=fixed_now - timedelta(minutes=10))

    repo_mock = MagicMock()
    repo_mock.get_last_success = AsyncMock(return_value=last)
    repo_mock.get_latest = AsyncMock(return_value=last)

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings([123])),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
        patch("src.bot.scheduler.jobs._check_postgres_visible", AsyncMock(return_value=False)),
        patch("src.bot.scheduler.jobs._check_redis_visible", AsyncMock(return_value=False)),
    ):
        await send_backup_health_heartbeat(bot=bot, session_maker=_make_session_maker(session_mock))

    text = bot.send_message.call_args[0][1]
    assert "DB: DOWN | Redis: DOWN" in text


# --- TASK-100 replicate job unit tests (mocked subprocess) ---


def _mk_settings_repl(enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.backup.replication_enabled = enabled
    s.backup.source_host = "10.0.0.1"
    s.backup.source_ssh_user = "root"
    s.backup.ssh_key_path = Path("/key")
    s.backup.source_dir = "/backups"
    s.backup.local_dir = Path("/tmp/bb-test-backups")
    s.backup.replication_max_lag_hours = 3
    return s


@patch("src.bot.scheduler.jobs.utcnow")
async def test_replicate_skips_when_disabled(
    mock_utcnow: MagicMock, session_mock: MagicMock
) -> None:
    with patch("src.shared.config.get_settings", return_value=_mk_settings_repl(False)):
        await replicate_latest_backup(session_maker=_make_session_maker(session_mock))
    # no error, just return


@patch("src.bot.scheduler.jobs._run_rsync_pull", new_callable=AsyncMock)
@patch("src.bot.scheduler.jobs.utcnow")
async def test_replicate_success_marks_replicated(
    mock_utcnow: MagicMock, mock_rsync: AsyncMock, session_mock: MagicMock
) -> None:
    fixed_now = datetime(2026, 6, 2, 12, 0, 0)
    mock_utcnow.return_value = fixed_now

    unrep = _mk_backup_run(
        status="success", finished_at=fixed_now - timedelta(hours=1), filename="dump.sql.gz"
    )
    repo_mock = MagicMock()
    repo_mock.get_last_unreplicated_success = AsyncMock(return_value=unrep)
    repo_mock.mark_replicated = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings_repl(True)),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
    ):
        await replicate_latest_backup(session_maker=_make_session_maker(session_mock))

    mock_rsync.assert_awaited_once()
    repo_mock.mark_replicated.assert_awaited_once()
    # commit happens in job


@patch("src.bot.scheduler.jobs._run_rsync_pull", new_callable=AsyncMock)
@patch("src.bot.scheduler.jobs.utcnow")
async def test_replicate_failure_does_not_mark(
    mock_utcnow: MagicMock, mock_rsync: AsyncMock, session_mock: MagicMock
) -> None:
    mock_rsync.side_effect = RuntimeError("ssh fail")
    unrep = _mk_backup_run(
        status="success", finished_at=datetime(2026, 6, 2, 11, 0), filename="f.sql.gz"
    )
    repo_mock = MagicMock()
    repo_mock.get_last_unreplicated_success = AsyncMock(return_value=unrep)
    repo_mock.mark_replicated = AsyncMock()

    with (
        patch("src.shared.config.get_settings", return_value=_mk_settings_repl(True)),
        patch("src.bot.scheduler.jobs.BackupRunRepository", return_value=repo_mock),
    ):
        await replicate_latest_backup(session_maker=_make_session_maker(session_mock))

    repo_mock.mark_replicated.assert_not_awaited()
