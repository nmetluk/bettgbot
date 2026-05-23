"""`SessionMiddleware` — открывает AsyncSession на update и кладёт в `data["session"]`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.shared.db import SessionLocal

__all__ = ["SessionMiddleware"]


class SessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # commit/rollback — на стороне сервиса. Контекст-менеджер закроет сессию,
        # если случится исключение.
        async with SessionLocal() as session:
            data["session"] = session
            return await handler(event, data)
