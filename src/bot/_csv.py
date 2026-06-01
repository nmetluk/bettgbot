"""Вспомогательные генераторы CSV для бота (TASK-097).

Все генераторы возвращают `BufferedInputFile` (готово к `bot.send_document`)
или `None` (например, если нет данных для CSV).
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from aiogram.types import BufferedInputFile

from src.shared.services.stats import CorrectUserRow


def generate_correct_users_csv(
    rows: list[CorrectUserRow],
    event_id: int,
) -> BufferedInputFile | None:
    """Генерирует CSV со списком угадавших пользователей для события.

    Формат: UTF-8 с BOM (utf-8-sig) — открывается корректно в Excel на Windows.
    Колонки: tg_user_id, first_name, last_name, tg_username, phone, outcome, predicted_at (ISO-8601 UTC).

    Если 0 угадавших — возвращает None (не прикладывать файл).
    """
    if not rows:
        return None

    fieldnames = [
        "tg_user_id",
        "first_name",
        "last_name",
        "tg_username",
        "phone",
        "outcome",
        "predicted_at",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for r in rows:
        writer.writerow(
            {
                "tg_user_id": r.tg_user_id,
                "first_name": r.first_name or "",
                "last_name": r.last_name or "",
                "tg_username": r.tg_username or "",
                "phone": r.phone,
                "outcome": r.outcome_label,
                "predicted_at": r.predicted_at.isoformat() if isinstance(r.predicted_at, datetime) else r.predicted_at,
            }
        )

    # encode с utf-8-sig добавляет BOM автоматически
    content = buffer.getvalue().encode("utf-8-sig")
    filename = f"correct_users_event_{event_id}.csv"
    return BufferedInputFile(content, filename=filename)
