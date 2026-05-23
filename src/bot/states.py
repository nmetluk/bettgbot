"""FSM-states aiogram, регистрируются в RedisStorage."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

__all__ = ["MakingPrediction"]


class MakingPrediction(StatesGroup):
    """FSM «Сделать прогноз»: 2 шага — выбор исхода → подтверждение."""

    choosing_outcome = State()
    confirming = State()
