"""Корневой класс декларативного маппинга SQLAlchemy 2.0.

`Base` фиксирует:
- naming convention для индексов/ограничений (читаемые имена в миграциях);
- type_annotation_map: `datetime` → `TIMESTAMP(timezone=True)`, `dict[str, Any]` → `JSONB`.

Модели импортируют только `Base`. Engine, session и миграции — TASK-006.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TIMESTAMP

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    # Для CHECK convention не добавляет префикс — имя берётся as-is из
    # `CheckConstraint(name=...)`. Это единообразно с поведением uq/fk/ix
    # (явное имя подавляет convention) и упрощает grep по полному имени.
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Корневой DeclarativeBase для всех моделей."""

    metadata = metadata_obj
    type_annotation_map: dict[Any, Any] = {  # noqa: RUF012
        datetime: TIMESTAMP(timezone=True),
        dict[str, Any]: JSONB,
    }
