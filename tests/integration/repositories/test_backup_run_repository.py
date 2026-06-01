"""Integration-тесты `BackupRunRepository` (TASK-099 amendment).

Фикстуры: несколько running/failed/success с разными finished_at.
Проверяем get_last_success (только success, самый свежий) и get_latest (любая, самая свежая по finished_at).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import BackupRun
from src.shared.repositories import BackupRunRepository

pytestmark = pytest.mark.integration


async def _insert_run(
    session: AsyncSession,
    *,
    status: str,
    finished_delta: timedelta | None,
    size: int | None = 10_000_000,
    host: str = "test-host",
    error: str | None = None,
    filename: str | None = None,
    replicated_at: datetime | None = None,
) -> BackupRun:
    now = datetime.now(tz=UTC)
    finished = now + finished_delta if finished_delta is not None else None
    run = BackupRun(
        started_at=now - timedelta(minutes=5),
        finished_at=finished,
        status=status,
        size_bytes=size,
        host=host,
        error=error,
        filename=filename,
        replicated_at=replicated_at,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def test_get_last_success_picks_only_success_latest(session: AsyncSession) -> None:
    """get_last_success возвращает только status=success, самый поздний finished_at."""
    # running (игнор)
    await _insert_run(session, status="running", finished_delta=None)
    # old success (игнор для get_last_success)
    await _insert_run(
        session, status="success", finished_delta=timedelta(hours=-10), filename="old.sql.gz"
    )
    # failed (игнор)
    await _insert_run(session, status="failed", finished_delta=timedelta(hours=-1), error="boom")
    # latest success
    latest_s = await _insert_run(
        session,
        status="success",
        finished_delta=timedelta(minutes=-5),
        filename="latest.sql.gz",
        replicated_at=datetime.now(tz=UTC),
    )

    repo = BackupRunRepository(session)
    got = await repo.get_last_success()

    assert got is not None
    assert got.id == latest_s.id
    assert got.status == "success"
    assert got.filename == "latest.sql.gz"
    assert got.replicated_at is not None


async def test_get_last_success_returns_none_if_no_success(session: AsyncSession) -> None:
    """Только running + failed → get_last_success = None."""
    await _insert_run(session, status="running", finished_delta=None)
    await _insert_run(session, status="failed", finished_delta=timedelta(minutes=-1), error="x")

    repo = BackupRunRepository(session)
    got = await repo.get_last_success()
    assert got is None


async def test_get_latest_returns_most_recent_any_status(session: AsyncSession) -> None:
    """get_latest возвращает самую свежую запись (по finished_at nulls_last + id), любого статуса."""
    await _insert_run(session, status="success", finished_delta=timedelta(hours=-5))
    recent_failed = await _insert_run(
        session, status="failed", finished_delta=timedelta(minutes=-1), error="fail"
    )
    # running без finished (должен быть "новее" если finished nulls last? но по коду order finished desc nulls_last)
    await _insert_run(session, status="running", finished_delta=None)

    repo = BackupRunRepository(session)
    got = await repo.get_latest()

    # В repo: order_by finished_at DESC nulls_last(), id DESC → running (null finished) должен быть последним?
    # nulls_last() с DESC значит nulls в конце, т.е. finished non-null первыми (свежие), потом nulls.
    # Поэтому recent_failed (finished недавно) должен выигрывать у running (null).
    assert got is not None
    assert got.id == recent_failed.id
    assert got.status == "failed"


async def test_get_latest_and_last_success_with_replication(session: AsyncSession) -> None:
    """Проверка, что replicated_at сохраняется и читается (для heartbeat отображения)."""
    await _insert_run(
        session,
        status="success",
        finished_delta=timedelta(minutes=-2),
        filename="rep.sql.gz",
        replicated_at=datetime.now(tz=UTC) - timedelta(minutes=1),
    )

    repo = BackupRunRepository(session)
    last = await repo.get_last_success()
    assert last is not None
    assert last.replicated_at is not None
    assert last.filename == "rep.sql.gz"
