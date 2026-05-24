"""Парсер свободного ввода интервала напоминания (TASK-015)."""

from __future__ import annotations

import re

__all__ = ["MAX_OFFSET_MINUTES", "MIN_OFFSET_MINUTES", "parse_offset"]


_OFFSET_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd]?)\s*$", re.IGNORECASE)

MIN_OFFSET_MINUTES = 5
MAX_OFFSET_MINUTES = 10080  # 7 дней


def parse_offset(raw: str) -> int | None:
    """Возвращает offset в минутах или `None`, если ввод невалиден.

    Поддерживаемые форматы:
      - `15`  → 15 минут (без суффикса = минуты)
      - `15m` → 15 минут
      - `1h`  → 60 минут
      - `2d`  → 2880 минут

    Граничные значения: 5 ≤ result ≤ 10080 (неделя). За границами → None.
    """
    match = _OFFSET_PATTERN.match(raw)
    if match is None:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "h":
        value *= 60
    elif unit == "d":
        value *= 1440
    if value < MIN_OFFSET_MINUTES or value > MAX_OFFSET_MINUTES:
        return None
    return value
