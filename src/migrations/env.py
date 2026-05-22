"""Alembic env.py — async вариант, читает Settings из src.shared.config.

Запускается из CLI alembic как отдельный процесс — поэтому здесь свой event loop
через `asyncio.run`, не пытаемся переиспользовать существующий.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from src.shared.config import settings
from src.shared.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline-режим: генерирует SQL-скрипт без подключения к БД."""
    context.configure(
        url=str(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # `set_main_option` не отражается в `get_section`, поэтому подмешиваем url
    # руками в копию секции [alembic] перед созданием engine.
    section = config.get_section(config.config_ini_section, {})
    if section is None:
        section = {}
    section["sqlalchemy.url"] = str(settings.database_url)
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Online-режим: подключается через async engine и применяет миграции."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
