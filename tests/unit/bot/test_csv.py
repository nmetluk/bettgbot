"""Unit-тесты для src/bot/_csv.py (TASK-097)."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest
from aiogram.types import BufferedInputFile
from src.bot._csv import generate_correct_users_csv
from src.shared.services.stats import CorrectUserRow


def _row(**kw: object) -> CorrectUserRow:
    base = {
        "tg_user_id": 111,
        "first_name": "Ivan",
        "last_name": "Petrov",
        "tg_username": "ivanp",
        "phone": "+79991234567",
        "outcome_label": "П1",
        "predicted_at": datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    }
    base.update(kw)
    return CorrectUserRow(**base)  # type: ignore[arg-type]


def test_generate_csv_returns_none_for_empty() -> None:
    assert generate_correct_users_csv([], 42) is None


def test_generate_csv_produces_buffered_file_with_bom_and_header() -> None:
    rows = [_row()]
    f = generate_correct_users_csv(rows, 123)
    assert isinstance(f, BufferedInputFile)
    assert f.filename == "correct_users_event_123.csv"
    # BOM + header
    raw = f.data
    assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM
    text = raw.decode("utf-8-sig")
    assert "tg_user_id,first_name,last_name,tg_username,phone,outcome,predicted_at" in text
    assert "111,Ivan,Petrov,ivanp,+79991234567,П1,2026-06-01T12:00:00+00:00" in text


def test_generate_csv_handles_nones_and_escapes() -> None:
    row = _row(last_name=None, tg_username=None, first_name="O'Reilly, Jr.")
    f = generate_correct_users_csv([row], 1)
    assert f is not None
    text = f.data.decode("utf-8-sig")
    # None -> empty, comma in name escaped by csv
    assert ",O'Reilly, Jr.,," in text or '"O\'Reilly, Jr."' in text
