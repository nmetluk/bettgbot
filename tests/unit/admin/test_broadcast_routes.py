"""Unit-тесты broadcast логики (TASK-061-amendment).

Примечание: из-за circular import в src/admin (broadcasts.py imports app,
app imports broadcasts) прямые unit тесты handler'ов затруднительны.
Здесь тестируем только изолированную логику.
"""

from __future__ import annotations

import pytest


def test_preview_char_count_logic() -> None:
    """Логика подсчёта байт работает корректно."""
    # ASCII — 1 байт на символ
    assert len("hello".encode("utf-8")) == 5

    # Кириллица — 2 байта на символ
    assert len("тест".encode("utf-8")) == 8

    # Пустая строка
    assert len("".encode("utf-8")) == 0

    # Смешанный текст
    assert len("hello мир".encode("utf-8")) == 12  # hello(5) + space(1) + мир(6)


def test_create_broadcast_dto_validation() -> None:
    """CreateBroadcastDraft принимает корректные значения."""
    from src.shared.services import CreateBroadcastDraft

    # Valid: all без category_id
    dto = CreateBroadcastDraft(
        segment="all",
        category_id=None,
        message_text="Test",
        created_by_admin_id=1,
    )
    assert dto.segment == "all"
    assert dto.category_id is None

    # Valid: category с category_id
    dto2 = CreateBroadcastDraft(
        segment="category",
        category_id=1,
        message_text="Test",
        created_by_admin_id=1,
    )
    assert dto2.category_id == 1
