"""Типизированные `CallbackData` для inline-клавиатур бота.

Префиксы короткие — лимит Telegram на `callback_data` 64 байта; чем короче
префикс, тем больше места под параметры.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

__all__ = ["CategoryCb", "CategoryListCb", "EventCb"]


class CategoryCb(CallbackData, prefix="c"):
    """Категория + страница. `category_id=None` означает «все категории»."""

    category_id: int | None
    page: int = 0


class EventCb(CallbackData, prefix="e"):
    """Открытие карточки события; `back_category_id` для возврата к списку."""

    event_id: int
    back_category_id: int | None


class CategoryListCb(CallbackData, prefix="cl"):
    """Возврат на список категорий — без параметров."""
