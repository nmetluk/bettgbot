"""Фабрики клавиатур бота. Только сборка — обработчиков здесь нет."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.shared.models import Category, Event, Outcome

from ..callbacks import (
    CategoryCb,
    CategoryListCb,
    EventCb,
    MyPredictionCb,
    MyTab,
    MyTabCb,
    PredictCancelCb,
    PredictConfirmCb,
    PredictPickCb,
    PredictStartCb,
)

__all__ = [
    "categories_kbd",
    "contact_request",
    "event_card_kbd",
    "events_in_category_kbd",
    "main_menu",
    "my_predictions_kbd",
    "predict_confirm_kbd",
    "predict_outcomes_kbd",
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


def event_card_kbd(
    *,
    event_id: int,
    back_button: tuple[str, CallbackData],
    can_predict: bool,
    has_prediction: bool,
    predict_back_category_id: int | None,
) -> InlineKeyboardMarkup:
    """Карточка события: опциональная «Сделать/Изменить прогноз» + произвольная кнопка «Назад».

    `back_button` — пара `(text, CallbackData)`. Это позволяет переиспользовать
    карточку из разных входных точек (каталог → «🔙 К событиям», «Мои прогнозы»
    → «🔙 К моим прогнозам»).

    `predict_back_category_id` нужен `PredictStartCb`, чтобы после отмены/конфирма
    FSM прогноза вернуть пользователя на список событий в категории. Когда вход
    был не из каталога, передаём `event.category_id` — пользователь приземлится
    в категории события, а не в исходной точке. Для MVP приемлемо.
    """
    builder = InlineKeyboardBuilder()
    if can_predict:
        predict_text = "✏️ Изменить прогноз" if has_prediction else "🎯 Сделать прогноз"
        builder.button(
            text=predict_text,
            callback_data=PredictStartCb(
                event_id=event_id, back_category_id=predict_back_category_id
            ),
        )
    back_text, back_cb = back_button
    builder.button(text=back_text, callback_data=back_cb)
    builder.adjust(1)
    return builder.as_markup()


def my_predictions_kbd(
    events: Sequence[Event],
    *,
    tab: MyTab,
    page: int,
    has_prev: bool,
    has_next: bool,
) -> InlineKeyboardMarkup:
    """Список «Мои прогнозы»: 1 кнопка на прогноз + ряд табов + опц. пагинация.

    Кнопок на прогноз ровно столько, сколько `events`. Тап → `MyPredictionCb`,
    `tab` нужен для возврата в ту же вкладку из карточки события. Маркер
    активного таба — `✓` в тексте кнопки (жирность в кнопках Telegram не доступна).
    «🏠 В меню» здесь не нужна — главное меню есть в постоянном ReplyKeyboard.
    """
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.button(
            text=event.title,
            callback_data=MyPredictionCb(event_id=event.id, tab=tab),
        )

    active_label = "✓ 🟢 Активные" if tab == "active" else "🟢 Активные"
    archive_label = "✓ 📦 Архив" if tab == "archive" else "📦 Архив"
    builder.button(text=active_label, callback_data=MyTabCb(tab="active", page=0))
    builder.button(text=archive_label, callback_data=MyTabCb(tab="archive", page=0))

    pagination_count = 0
    if has_prev:
        builder.button(text="‹", callback_data=MyTabCb(tab=tab, page=page - 1))
        pagination_count += 1
    if has_next:
        builder.button(text="›", callback_data=MyTabCb(tab=tab, page=page + 1))
        pagination_count += 1

    layout = [1] * len(events) + [2]
    if pagination_count > 0:
        layout.append(pagination_count)
    builder.adjust(*layout)
    return builder.as_markup()


def predict_outcomes_kbd(
    event_id: int,
    outcomes: Sequence[Outcome],
    back_category_id: int | None,
) -> InlineKeyboardMarkup:
    """Список исходов для выбора + «❌ Отмена»."""
    builder = InlineKeyboardBuilder()
    for i, outcome in enumerate(outcomes):
        builder.button(
            text=f"{i + 1}) {outcome.label}",
            callback_data=PredictPickCb(event_id=event_id, outcome_id=outcome.id),
        )
    builder.button(
        text="❌ Отмена",
        callback_data=PredictCancelCb(event_id=event_id, back_category_id=back_category_id),
    )
    builder.adjust(1)
    return builder.as_markup()


def predict_confirm_kbd(
    event_id: int,
    outcome_id: int,
    back_category_id: int | None,
) -> InlineKeyboardMarkup:
    """Подтверждение прогноза: «✅ Подтвердить» + «🔙 Назад»."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Подтвердить",
        callback_data=PredictConfirmCb(event_id=event_id, outcome_id=outcome_id),
    )
    # «🔙 Назад» — повторный заход в `choosing_outcome` через PredictStartCb.
    builder.button(
        text="🔙 Назад",
        callback_data=PredictStartCb(event_id=event_id, back_category_id=back_category_id),
    )
    builder.adjust(2)
    return builder.as_markup()
