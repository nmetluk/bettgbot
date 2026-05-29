"""Integration-тесты на применение `0001_init` к настоящему PostgreSQL.

Запускаются под маркером `integration` — отдельным CI-job'ом с postgres-сервисом.
Локально: `make up` (compose с postgres) + `uv run pytest tests/integration -m integration`.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dotenv(path: str) -> None:
    """Минимальный loader для `.env`. В CI .env нет — переменные приходят из workflow."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(os.path.join(REPO_ROOT, ".env"))

# DATABASE_URL берём из env (наполненного workflow в CI или `.env` локально).
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Запускает alembic из корня репо с пробросом env."""
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture()
def fresh_db() -> Iterator[None]:
    """Перед каждым тестом: downgrade до base. После — возвращаем БД на head,
    чтобы последующие тесты (repository-тесты) видели актуальную схему.
    """
    _alembic("downgrade", "base")
    try:
        yield
    finally:
        _alembic("upgrade", "head")


pytestmark = pytest.mark.integration


async def _fetch_scalars(query: str) -> list[str]:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            return [row[0] for row in result.all()]
    finally:
        await engine.dispose()


async def test_upgrade_creates_all_tables(fresh_db: None) -> None:
    _alembic("upgrade", "head")
    tables = await _fetch_scalars(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    expected = {
        "admin_user",
        "alembic_version",
        "audit_log",
        "category",
        "event",
        "outcome",
        "prediction",
        "reminder_dispatch_log",
        "reminder_setting",
        "user",
    }
    assert set(tables) >= expected, f"missing: {expected - set(tables)}"


async def test_0002_creates_reminder_dispatch_log_with_unique_constraint(
    fresh_db: None,
) -> None:
    _alembic("upgrade", "head")
    constraints = await _fetch_scalars("SELECT conname FROM pg_constraint WHERE contype='u'")
    assert "uq_reminder_dispatch_log_user_event_offset" in constraints


async def test_upgrade_creates_indexes(fresh_db: None) -> None:
    _alembic("upgrade", "head")
    indexes = await _fetch_scalars("SELECT indexname FROM pg_indexes WHERE schemaname='public'")
    expected = {
        "ix_event_predictions_close_at_active",
        "ix_event_is_published_is_archived_starts_at",
        "uq_prediction_user_event",
    }
    assert set(indexes) >= expected, f"missing: {expected - set(indexes)}"


async def test_upgrade_creates_check_constraints(fresh_db: None) -> None:
    _alembic("upgrade", "head")
    constraints = await _fetch_scalars("SELECT conname FROM pg_constraint WHERE contype='c'")
    assert "ck_event_close_before_start" in constraints
    assert "ck_event_result_archive_consistency" in constraints


async def test_0003_relax_event_archive_check(fresh_db: None) -> None:
    """После 0003 CHECK разрешает «архивный без result_outcome_id», но требует archived_at."""
    from sqlalchemy.exc import IntegrityError

    _alembic("upgrade", "head")

    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.begin() as conn:
            admin_id = (
                await conn.execute(
                    text(
                        "INSERT INTO admin_user (login, password_hash) "
                        "VALUES ('a', 'h') RETURNING id"
                    )
                )
            ).scalar_one()
            category_id = (
                await conn.execute(
                    text(
                        "INSERT INTO category (name, slug, sort_order, is_active) "
                        "VALUES ('C', 'c-0003', 0, true) RETURNING id"
                    )
                )
            ).scalar_one()

            # 1) Архивный без итога, с archived_at — после 0003 разрешено.
            await conn.execute(
                text(
                    """
                    INSERT INTO event (
                      category_id, title, metadata, starts_at,
                      predictions_close_at, is_published, is_archived,
                      archived_at, created_by_admin_id
                    ) VALUES (
                      :cat, 'arch-no-result', '{}'::jsonb, now() - interval '10 days',
                      now() - interval '10 days', true, true, now(), :adm
                    )
                    """
                ),
                {"cat": category_id, "adm": admin_id},
            )

        # 2) Архивный без archived_at — нарушение нового CHECK.
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO event (
                          category_id, title, metadata, starts_at,
                          predictions_close_at, is_published, is_archived,
                          archived_at, created_by_admin_id
                        ) VALUES (
                          :cat, 'arch-no-at', '{}'::jsonb, now() - interval '10 days',
                          now() - interval '10 days', true, true, NULL, :adm
                        )
                        """
                    ),
                    {"cat": category_id, "adm": admin_id},
                )

        # Cleanup: убираем созданное, иначе fresh_db.downgrade base в следующем
        # тесте упадёт (0003→0002 возвращает строгий CHECK).
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE event, category, admin_user CASCADE"))
    finally:
        await engine.dispose()


async def test_downgrade_drops_everything(fresh_db: None) -> None:
    _alembic("upgrade", "head")
    _alembic("downgrade", "base")
    tables = await _fetch_scalars("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    # После downgrade base — только alembic_version (служебная) остаётся.
    assert set(tables) == {"alembic_version"}, f"unexpected: {tables}"


async def test_0004_creates_dispatch_log_indexes(fresh_db: None) -> None:
    """После 0004 на reminder_dispatch_log есть индексы на FK и dispatched_at (TASK-048)."""
    _alembic("upgrade", "head")
    indexes = await _fetch_scalars(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
        "AND tablename='reminder_dispatch_log' AND indexname NOT LIKE 'pk_%' "
        "ORDER BY indexname"
    )
    expected = {
        "ix_reminder_dispatch_log_dispatched_at",
        "ix_reminder_dispatch_log_event_id",
        "ix_reminder_dispatch_log_user_id",
        "uq_reminder_dispatch_log_user_event_offset",  # из 0002
    }
    assert set(indexes) == expected, (
        f"unexpected: {set(indexes) - expected}, missing: {expected - set(indexes)}"
    )


async def test_0004_roundtrip(fresh_db: None) -> None:
    """Upgrade+downgrade 0004 оставляют схему валидной (TASK-048, TASK-049 chain через 0003b)."""
    _alembic("upgrade", "0003_relax_event_archive")
    _alembic("upgrade", "0003b_fix_alembic_version_type")
    _alembic("upgrade", "0004_reminder_dispatch_log_indexes")
    _alembic("downgrade", "0003b_fix_alembic_version_type")

    # После downgrade индексы 0004 должны исчезнуть.
    indexes = await _fetch_scalars(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
        "AND tablename='reminder_dispatch_log' AND indexname NOT LIKE 'pk_%' "
        "ORDER BY indexname"
    )
    # Остался только unique constraint из 0002 (он реализован через индекс).
    assert indexes == ["uq_reminder_dispatch_log_user_event_offset"]
