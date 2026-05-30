"""Time utilities — единая точка для операций с datetime.

Во всём проекте используется **aware UTC**:
- Колонки в БД: `TIMESTAMP(timezone=True)` (см. `Base.type_annotation_map`)
- Код: `datetime.now(tz=UTC)` или helper `utcnow()`
- Запрещено: `datetime.utcnow()` (deprecated in Python 3.12) и naive datetime
"""

from __future__ import annotations

from datetime import UTC, datetime

UTC = UTC


def utcnow() -> datetime:
    """Текущий момент времени в UTC как aware datetime.

    Замена deprecated `datetime.utcnow()` (naive).
    Используется везде для получения текущего времени.
    """
    return datetime.now(tz=UTC)
