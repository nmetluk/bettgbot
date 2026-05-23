"""`LoggingMiddleware` — структурный лог update'а: request_id, latency, outcome."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.shared.logging import get_logger

__all__ = ["LoggingMiddleware"]


logger = get_logger(__name__)


def _extract_user_id(event: TelegramObject) -> int | None:
    """Возвращает `tg_user_id`, если апдейт содержит `from_user`."""
    from_user = getattr(event, "from_user", None)
    if from_user is None:
        # Update сам по себе не имеет from_user; смотрим вложенные.
        for attr in ("message", "callback_query", "inline_query", "edited_message"):
            inner = getattr(event, attr, None)
            if inner is not None and getattr(inner, "from_user", None) is not None:
                return int(inner.from_user.id)
        return None
    return int(from_user.id)


def _extract_update_id(event: TelegramObject) -> int | None:
    return getattr(event, "update_id", None)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        request_id = uuid.uuid4().hex[:12]
        update_id = _extract_update_id(event)
        tg_user_id = _extract_user_id(event)

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            update_id=update_id,
            tg_user_id=tg_user_id,
        )
        t0 = time.monotonic()
        try:
            result = await handler(event, data)
        except Exception as exc:
            logger.warning(
                "bot.update.failed",
                latency_ms=int((time.monotonic() - t0) * 1000),
                exception_type=type(exc).__name__,
            )
            raise
        else:
            logger.info(
                "bot.update.handled",
                latency_ms=int((time.monotonic() - t0) * 1000),
                outcome="ok",
            )
            return result
        finally:
            structlog.contextvars.clear_contextvars()
