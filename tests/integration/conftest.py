"""Общий conftest для integration-тестов.

- Загружает `.env` локально (в CI переменные приходят через workflow `env:`).
- Применяет миграции до `head` один раз на сессию тестов.
- Предоставляет фикстуру `session` с rollback после теста и набор helper-фабрик
  (`make_admin`, `make_category`, `make_user`, `make_event`, `make_outcome`).

Две session-фикстуры:

- `session` (здесь) — простой rollback в финале. Подходит для repository-тестов,
  которые **не вызывают** `session.commit()`.
- `nested_session` (в `tests/integration/services/conftest.py`) — внешняя
  транзакция + SAVEPOINT для тестов сервисов, которые `commit()` внутри;
  SAVEPOINT откатывается, поэтому коммит не персистится. listener
  `after_transaction_end` переоткрывает SAVEPOINT после каждого commit.
"""

from __future__ import annotations

import itertools
import os
import subprocess
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_dotenv(path: str) -> None:
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


@pytest.fixture(scope="session", autouse=True)
def _migrations_applied() -> None:
    """Гарантирует, что схема находится на head перед repository-тестами.

    `alembic upgrade head` идемпотентен: no-op, если уже head.
    """
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )


@pytest_asyncio.fixture()
async def session() -> AsyncIterator[AsyncSession]:
    """Открывает AsyncSession, прогоняет тест, делает rollback — данные не сохраняются.

    Создаём собственный engine с `NullPool` на каждый тест: pytest-asyncio даёт
    каждому тесту свой event loop, а engine из `src.shared.db` привязан к loop'у
    при первом подключении — в результате на втором тесте получаем
    `RuntimeError: Event loop is closed`. Per-test engine + NullPool обходят это.
    """
    # Импорт здесь, чтобы `_load_dotenv` уже отработал.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from src.shared.config import settings

    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with sm() as s:
            try:
                yield s
            finally:
                await s.rollback()
    finally:
        await engine.dispose()


_counter = itertools.count(1)


def _uniq(prefix: str) -> str:
    """Уникальный человекочитаемый id для тестовых полей."""
    return f"{prefix}-{next(_counter)}-{uuid.uuid4().hex[:6]}"


def _uniq_int() -> int:
    """Уникальный 63-bit int для tg_user_id/phone-numeric."""
    return uuid.uuid4().int & ((1 << 62) - 1)


async def make_admin(session: AsyncSession, **overrides: Any) -> Any:
    from src.shared.models import AdminUser

    defaults: dict[str, Any] = {
        "login": _uniq("admin"),
        "password_hash": "bcrypt-stub",
        "full_name": None,
    }
    admin = AdminUser(**{**defaults, **overrides})
    session.add(admin)
    await session.flush()
    return admin


async def make_category(session: AsyncSession, **overrides: Any) -> Any:
    from src.shared.models import Category

    defaults: dict[str, Any] = {
        "name": _uniq("Cat"),
        "slug": _uniq("cat"),
        "sort_order": 0,
        "is_active": True,
    }
    category = Category(**{**defaults, **overrides})
    session.add(category)
    await session.flush()
    return category


async def make_user(session: AsyncSession, **overrides: Any) -> Any:
    from src.shared.models import User

    defaults: dict[str, Any] = {
        "tg_user_id": _uniq_int(),
        "phone": f"+7{_uniq_int() % 10_000_000_000:010d}",
        "tg_username": _uniq("tg"),
        "first_name": "Test",
        "last_name": None,
    }
    user = User(**{**defaults, **overrides})
    session.add(user)
    await session.flush()
    return user


async def make_event(
    session: AsyncSession,
    *,
    category: Any | None = None,
    admin: Any | None = None,
    **overrides: Any,
) -> Any:
    from src.shared.models import Event

    if category is None:
        category = await make_category(session)
    if admin is None:
        admin = await make_admin(session)
    starts = datetime.now(tz=UTC) + timedelta(days=1)
    defaults: dict[str, Any] = {
        "category_id": category.id,
        "title": _uniq("Event"),
        "description": None,
        "metadata_": {},
        "starts_at": starts,
        "predictions_close_at": starts - timedelta(minutes=10),
        "created_by_admin_id": admin.id,
    }
    event = Event(**{**defaults, **overrides})
    session.add(event)
    await session.flush()
    return event


async def make_outcome(session: AsyncSession, event_id: int, **overrides: Any) -> Any:
    from src.shared.models import Outcome

    defaults: dict[str, Any] = {
        "event_id": event_id,
        "label": _uniq("Outcome"),
        "sort_order": 0,
    }
    outcome = Outcome(**{**defaults, **overrides})
    session.add(outcome)
    await session.flush()
    return outcome
