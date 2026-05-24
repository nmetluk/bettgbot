"""FSM-states aiogram, регистрируются в RedisStorage."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

__all__ = ["EditingReminders", "MakingPrediction"]


class MakingPrediction(StatesGroup):
    """FSM «Сделать прогноз»: 2 шага — выбор исхода → подтверждение."""

    choosing_outcome = State()
    confirming = State()


class EditingReminders(StatesGroup):
    """FSM настройки напоминаний.

    - `adding_offset` — пользователь нажал «✍️ Свой ввод» и шлёт текстовое
      сообщение с интервалом.
    """

    adding_offset = State()
