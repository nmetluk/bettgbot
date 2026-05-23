"""Фабрики клавиатур бота. Только сборка — обработчиков здесь нет."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.shared.models import Category, Event

from ..callbacks import CategoryCb, CategoryListCb, EventCb

__all__ = [
    "categories_kbd",
    "contact_request",
    "event_card_kbd",
    "events_in_category_kbd",
    "main_menu",
]


def main_menu() -> ReplyKeyboardMarkup:
    """Постоянное главное меню бота (см. docs/04-bot-flows.md)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📅 Все события"),
                KeyboardButton(text="🎯 Сделать прогноз"),
            ],
            [
                KeyboardButton(text="📋 Мои прогнозы"),
                KeyboardButton(text="🔔 Напоминания"),
            ],
            [KeyboardButton(text="ℹ️ Справка")],
        ],
        resize_keyboard=True,
    )


def contact_request() -> ReplyKeyboardMarkup:
    """Одна кнопка `request_contact=True` для шага регистрации (TASK-011)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def categories_kbd(
    categories_with_counts: Sequence[tuple[Category, int]], total: int
) -> InlineKeyboardMarkup:
    """Список категорий + pseudo-«все категории» с числом активных событий."""
    builder = InlineKeyboardBuilder()
    for cat, count in categories_with_counts:
        builder.button(
            text=f"{cat.name} ({count})",
            callback_data=CategoryCb(category_id=cat.id, page=0),
        )
    builder.button(
        text=f"🗂 Все категории ({total})",
        callback_data=CategoryCb(category_id=None, page=0),
    )
    builder.adjust(1)
    return builder.as_markup()


def events_in_category_kbd(
    events: Sequence[Event],
    *,
    page: int,
    has_prev: bool,
    has_next: bool,
    category_id: int | None,
) -> InlineKeyboardMarkup:
    """Список событий с пагинацией + «🔙 К категориям»."""
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.button(
            text=f"{event.title} — {event.starts_at:%d.%m %H:%M}",
            callback_data=EventCb(event_id=event.id, back_category_id=category_id),
        )
    builder.adjust(1)

    pagination_row: list = []  # type: ignore[type-arg]
    if has_prev:
        builder.button(
            text="‹",
            callback_data=CategoryCb(category_id=category_id, page=page - 1),
        )
        pagination_row.append(1)
    if has_next:
        builder.button(
            text="›",
            callback_data=CategoryCb(category_id=category_id, page=page + 1),
        )
        pagination_row.append(1)

    builder.button(text="🔙 К категориям", callback_data=CategoryListCb())

    # Структура: по одному event на ряд (через .adjust выше), потом ряд пагинации,
    # потом ряд с «🔙 К категориям».
    layout = [1] * len(events)
    if pagination_row:
        layout.append(len(pagination_row))
    layout.append(1)
    builder.adjust(*layout)
    return builder.as_markup()


def event_card_kbd(*, back_category_id: int | None) -> InlineKeyboardMarkup:
    """Карточка события: пока только «🔙 К событиям» (TASK-013 добавит «Сделать прогноз»)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔙 К событиям",
        callback_data=CategoryCb(category_id=back_category_id, page=0),
    )
    return builder.as_markup()
