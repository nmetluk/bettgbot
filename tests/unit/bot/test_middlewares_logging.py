"""Тесты `LoggingMiddleware`."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
import structlog
from src.bot.middlewares.logging import LoggingMiddleware

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    # configure_logging из других тестов может оставить root handlers; чистим.
    yield
    logging.getLogger().handlers.clear()
    structlog.contextvars.clear_contextvars()


class _FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _FakeUpdate:
    def __init__(self, *, update_id: int | None = 1, from_user: _FakeUser | None = None) -> None:
        self.update_id = update_id
        self.from_user = from_user


async def _handler_ok(event: Any, data: dict[str, Any]) -> str:
    return "ok"


async def _handler_raises(event: Any, data: dict[str, Any]) -> None:
    raise RuntimeError("boom")


async def test_logging_middleware_binds_contextvars() -> None:
    captured: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> str:
        captured.update(structlog.contextvars.get_contextvars())
        return "ok"

    mw = LoggingMiddleware()
    update = _FakeUpdate(update_id=42, from_user=_FakeUser(user_id=7))
    result = await mw(handler, update, {})

    assert result == "ok"
    assert captured["update_id"] == 42
    assert captured["tg_user_id"] == 7
    assert "request_id" in captured
    # После теста контекст должен быть чист (clear_contextvars в finally).
    assert structlog.contextvars.get_contextvars() == {}


async def test_logging_middleware_logs_latency(capsys: pytest.CaptureFixture[str]) -> None:
    from src.shared.logging import configure_logging

    configure_logging("INFO", "json")
    mw = LoggingMiddleware()
    update = _FakeUpdate()
    await mw(_handler_ok, update, {})

    output = _ANSI_RE.sub("", capsys.readouterr().err + capsys.readouterr().out)
    line = next((s for s in output.splitlines() if "bot.update.handled" in s), None)
    assert line is not None, f"event not logged: {output!r}"
    assert "latency_ms" in line


async def test_logging_middleware_logs_exception() -> None:
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    typed_handler: Callable[[Any, dict[str, Any]], Awaitable[Any]] = handler
    mw = LoggingMiddleware()
    update = _FakeUpdate()
    with pytest.raises(RuntimeError, match="boom"):
        await mw(typed_handler, update, {})
    # Контекст вычищен даже при исключении.
    assert structlog.contextvars.get_contextvars() == {}
