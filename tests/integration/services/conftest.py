"""Conftest для service-тестов.

Сервисы делают `commit()` — обычная `rollback`-фикстура из `tests/integration/conftest.py`
для них не работает (закоммиченные данные останутся между тестами).

Стандартное решение — внешняя транзакция + nested SAVEPOINT'ы. Сервисный
`commit()` коммитит savepoint, листенер `after_transaction_end` сразу открывает
новый, а в teardown мы откатываем внешнюю транзакцию целиком.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture()
async def nested_session() -> AsyncIterator[AsyncSession]:
    """Сессия с вложенным SAVEPOINT'ом: сервис может делать `commit()` без последствий.

    Cм. https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction
    """
    from src.shared.config import settings

    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            outer = await conn.begin()
            session = AsyncSession(bind=conn, expire_on_commit=False)
            await session.begin_nested()

            @sa_event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sync_sess: Any, transaction: Any) -> None:
                if transaction.nested and not transaction._parent.nested:
                    sync_sess.begin_nested()

            try:
                yield session
            finally:
                await session.close()
                await outer.rollback()
    finally:
        await engine.dispose()
