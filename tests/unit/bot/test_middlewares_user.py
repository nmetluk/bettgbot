"""Тесты `UserMiddleware` (mock-уровень, без БД)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.bot.middlewares.user import UserMiddleware


class _FakeUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _FakeUpdate:
    def __init__(self, from_user: _FakeUser | None) -> None:
        self.from_user = from_user
        self.update_id = 1


def _patch_user_lookup(
    monkeypatch: pytest.MonkeyPatch, *, found_user: Any | None
) -> tuple[AsyncMock, AsyncMock]:
    """Подменяет UserRepository.get_by_tg_user_id и UserService.touch_last_seen."""
    get_by_tg = AsyncMock(return_value=found_user)
    touch = AsyncMock(return_value=None)

    repo_factory = MagicMock(return_value=MagicMock(get_by_tg_user_id=get_by_tg))
    service_factory = MagicMock(return_value=MagicMock(touch_last_seen=touch))

    monkeypatch.setattr("src.bot.middlewares.user.UserRepository", repo_factory)
    monkeypatch.setattr("src.bot.middlewares.user.UserService", service_factory)
    return get_by_tg, touch


async def test_user_middleware_injects_user_when_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db_user = MagicMock(id=99)
    get_by_tg, touch = _patch_user_lookup(monkeypatch, found_user=fake_db_user)

    captured: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> str:
        captured["user"] = data.get("user")
        return "ok"

    mw = UserMiddleware()
    update = _FakeUpdate(from_user=_FakeUser(user_id=7))
    data = {"session": MagicMock(name="Session")}
    result = await mw(handler, update, data)

    assert result == "ok"
    assert captured["user"] is fake_db_user
    get_by_tg.assert_awaited_once_with(7)
    touch.assert_awaited_once_with(99)


async def test_user_middleware_injects_none_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _get_by_tg, touch = _patch_user_lookup(monkeypatch, found_user=None)

    captured: dict[str, Any] = {}

    async def handler(event: Any, data: dict[str, Any]) -> str:
        captured["user"] = data.get("user")
        return "ok"

    mw = UserMiddleware()
    update = _FakeUpdate(from_user=_FakeUser(user_id=7))
    data = {"session": MagicMock(name="Session")}
    await mw(handler, update, data)

    assert captured["user"] is None
    touch.assert_not_awaited()


async def test_user_middleware_no_from_user_skips_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_by_tg, touch = _patch_user_lookup(monkeypatch, found_user=None)
    handler = AsyncMock(return_value="ok")
    mw = UserMiddleware()
    update = _FakeUpdate(from_user=None)
    result = await mw(handler, update, {"session": MagicMock()})
    assert result == "ok"
    get_by_tg.assert_not_awaited()
    touch.assert_not_awaited()
