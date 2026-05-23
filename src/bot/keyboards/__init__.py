"""Фабрики клавиатур бота. Только сборка — обработчиков здесь нет."""

from __future__ import annotations

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

__all__ = ["contact_request", "main_menu"]


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
