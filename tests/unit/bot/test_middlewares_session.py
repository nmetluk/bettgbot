"""Тесты `SessionMiddleware`."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.bot.middlewares.session import SessionMiddleware


class _AsyncContext:
    """Минимальный async ctx manager для подмены SessionLocal()."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Any:
        self.entered = True
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.exited = True


async def test_session_middleware_injects_session(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = MagicMock(name="AsyncSession")
    ctx = _AsyncContext(fake_session)
    monkeypatch.setattr("src.bot.middlewares.session.SessionLocal", lambda: ctx)

    captured: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> str:
        captured["session"] = data.get("session")
        return "ok"

    mw = SessionMiddleware()
    result = await mw(handler, MagicMock(name="Update"), {})
    assert result == "ok"
    assert captured["session"] is fake_session
    assert ctx.entered and ctx.exited


async def test_session_middleware_closes_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = MagicMock(name="AsyncSession")
    ctx = _AsyncContext(fake_session)
    monkeypatch.setattr("src.bot.middlewares.session.SessionLocal", lambda: ctx)

    handler = AsyncMock(side_effect=RuntimeError("boom"))
    mw = SessionMiddleware()
    with pytest.raises(RuntimeError, match="boom"):
        await mw(handler, MagicMock(name="Update"), {})
    assert ctx.entered is True
    assert ctx.exited is True
