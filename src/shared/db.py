"""Async engine + sessionmaker для всех сервисов.

Используется через DI (`get_session`) — FastAPI берёт через `Depends`,
aiogram — через middleware. Глобальной открытой сессии нет: любой потребитель
открывает свою через `async with SessionLocal()` или (предпочтительно)
получает её из `get_session()` как зависимость.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

__all__ = ["SessionLocal", "engine", "get_session"]


# `pool_pre_ping=True` — лёгкий SELECT 1 перед выдачей соединения; спасает от
# мёртвых соединений после рестарта Postgres / firewall idle-timeout.
engine: AsyncEngine = create_async_engine(
    str(settings.database_url),
    echo=False,
    pool_pre_ping=True,
)

# `expire_on_commit=False` обязателен для async: иначе после `commit()`
# атрибуты объектов считаются протухшими и любое обращение к ним запускает
# implicit IO в (теперь закрытом) контексте.
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Async-генератор для DI: открывает сессию, отдаёт её, закрывает в finally."""
    async with SessionLocal() as session:
        yield session
