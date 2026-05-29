"""Тесты leaderboard-handler'а (TASK-058)."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.admin.routes.leaderboard import _session_dep
from src.shared.models import AdminUser
from src.shared.services import LeaderboardRow


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    return a


async def _bypass_session() -> Any:
    yield MagicMock()


@pytest.fixture()
def fake_admin_middleware_session() -> Generator[None, None, None]:
    """Патчит middleware'овский SessionLocal так, чтобы вернуть fake admin."""

    async def _get(model: object, pk: object) -> AdminUser | None:
        return _make_admin()

    fake_session = MagicMock()
    fake_session.get = _get

    @asynccontextmanager
    async def _cm() -> Any:
        yield fake_session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    with patch("src.admin.auth.middleware.SessionLocal", maker):
        yield


def _client(service_mock: MagicMock) -> TestClient:
    app.dependency_overrides[current_admin] = lambda: _make_admin()
    app.dependency_overrides[_session_dep] = _bypass_session
    import src.admin.routes.leaderboard as lb_routes

    lb_routes.StatsService = lambda session: service_mock  # type: ignore[attr-defined,assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def test_leaderboard_renders_rows(fake_admin_middleware_session: None) -> None:
    """Handler вызывает сервис и рендерит строки рейтинга."""
    service = MagicMock()
    service.leaderboard = AsyncMock(
        return_value=[
            LeaderboardRow(
                rank=1,
                user_id=1,
                display_name="Alice Wonder",
                correct=5,
                resolved=5,
                accuracy=100.0,
            ),
            LeaderboardRow(
                rank=2,
                user_id=2,
                display_name="Bob Builder",
                correct=3,
                resolved=5,
                accuracy=60.0,
            ),
        ]
    )

    client = _client(service)
    response = client.get("/leaderboard")

    assert response.status_code == 200
    service.leaderboard.assert_awaited_once_with(min_resolved=5, limit=100, period_days=None)

    content = response.text
    assert "Alice Wonder" in content
    assert "Bob Builder" in content
    assert "100%" in content
    assert "60.0%" in content
    assert "1" in content  # rank
    assert "2" in content  # rank


def test_leaderboard_empty_state(fake_admin_middleware_session: None) -> None:
    """Handler отображает пустое состояние, когда рейтинг пуст."""
    service = MagicMock()
    service.leaderboard = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/leaderboard")

    assert response.status_code == 200
    content = response.text
    assert "пока никто" in content.lower() or "минимум 5" in content.lower()


def test_leaderboard_period_filter(fake_admin_middleware_session: None) -> None:
    """Handler передаёт period_days в сервис при query-параметре."""
    service = MagicMock()
    service.leaderboard = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/leaderboard?period=30d")

    assert response.status_code == 200
    service.leaderboard.assert_awaited_once_with(min_resolved=5, limit=100, period_days=30)


def test_leaderboard_period_all(fake_admin_middleware_session: None) -> None:
    """Параметр period=all передаёт None в сервис."""
    service = MagicMock()
    service.leaderboard = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/leaderboard?period=all")

    assert response.status_code == 200
    service.leaderboard.assert_awaited_once_with(min_resolved=5, limit=100, period_days=None)


def test_leaderboard_invalid_period_rejected(fake_admin_middleware_session: None) -> None:
    """Некорректный period возвращает 422."""
    service = MagicMock()
    service.leaderboard = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/leaderboard?period=invalid")

    assert response.status_code == 422
