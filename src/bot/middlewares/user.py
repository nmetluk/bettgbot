"""`UserMiddleware` — находит `User` по `tg_user_id` и кладёт в `data["user"]`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.repositories import UserRepository
from src.shared.services import UserService

__all__ = ["UserMiddleware"]


def _extract_tg_user_id(event: TelegramObject) -> int | None:
    from_user = getattr(event, "from_user", None)
    if from_user is not None:
        return int(from_user.id)
    for attr in ("message", "callback_query", "inline_query", "edited_message"):
        inner = getattr(event, attr, None)
        if inner is not None and getattr(inner, "from_user", None) is not None:
            return int(inner.from_user.id)
    return None


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user_id = _extract_tg_user_id(event)
        if tg_user_id is None:
            data["user"] = None
            return await handler(event, data)

        session: AsyncSession = data["session"]
        user = await UserRepository(session).get_by_tg_user_id(tg_user_id)
        data["user"] = user
        if user is not None:
            # UserService не требует registry (открытая регистрация).
            await UserService(session).touch_last_seen(user.id)
        return await handler(event, data)
