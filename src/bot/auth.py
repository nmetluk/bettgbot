"""Декоратор `@require_active_user` — проверка регистрации и блокировки на handler'ах бота."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from aiogram.types import CallbackQuery, Message

from src.shared.models import User

from . import texts

__all__ = ["require_active_user"]


def _deny_text(user: User | None) -> str | None:
    if user is None:
        return texts.NEED_START
    if user.is_blocked:
        return texts.ACCESS_DENIED
    return None


def require_active_user(
    handler: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Перед handler'ом проверяет `user`: None → NEED_START, blocked → ACCESS_DENIED.

    Handler принимает первым позиционным аргументом `Message` или `CallbackQuery`,
    в kwargs — `user: User | None`. Если deny — отвечаем (alert для callback,
    обычный answer для message) и возвращаем None; handler не вызывается.
    Тип `user` в сигнатуре handler'а формально остаётся `User | None`, но
    логически после декоратора он гарантированно не None и не blocked —
    handler не должен повторять проверку.
    """

    @wraps(handler)
    async def wrapper(event: Message | CallbackQuery, *args: Any, **kwargs: Any) -> Any:
        user: User | None = kwargs.get("user")
        deny = _deny_text(user)
        if deny is not None:
            if isinstance(event, CallbackQuery):
                await event.answer(deny, show_alert=True)
            else:
                await event.answer(deny)
            return None
        return await handler(event, *args, **kwargs)

    return wrapper
