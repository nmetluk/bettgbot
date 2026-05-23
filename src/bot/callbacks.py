"""Типизированные `CallbackData` для inline-клавиатур бота.

Префиксы короткие — лимит Telegram на `callback_data` 64 байта; чем короче
префикс, тем больше места под параметры.
"""

from __future__ import annotations

from typing import Literal

from aiogram.filters.callback_data import CallbackData

__all__ = [
    "CategoryCb",
    "CategoryListCb",
    "EventCb",
    "MyPredictionCb",
    "MyTab",
    "MyTabCb",
    "PredictCancelCb",
    "PredictConfirmCb",
    "PredictPickCb",
    "PredictStartCb",
]


MyTab = Literal["active", "archive"]


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


class PredictStartCb(CallbackData, prefix="p"):
    """Старт FSM прогноза из карточки события."""

    event_id: int
    back_category_id: int | None


class PredictPickCb(CallbackData, prefix="po"):
    """Выбран исход — переход к шагу подтверждения."""

    event_id: int
    outcome_id: int


class PredictConfirmCb(CallbackData, prefix="pc"):
    """Финальное подтверждение прогноза."""

    event_id: int
    outcome_id: int


class PredictCancelCb(CallbackData, prefix="px"):
    """Отмена прогноза — возврат на карточку события."""

    event_id: int
    back_category_id: int | None


class MyTabCb(CallbackData, prefix="m"):
    """Раздел «Мои прогнозы»: переключение вкладки и пагинация."""

    tab: MyTab
    page: int = 0


class MyPredictionCb(CallbackData, prefix="mp"):
    """Тап на конкретный прогноз; `tab` нужен, чтобы кнопка «Назад» вернула в ту же вкладку."""

    event_id: int
    tab: MyTab
