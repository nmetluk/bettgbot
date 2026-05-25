"""Тесты dashboard-handler'а (TASK-043)."""

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
from src.admin.routes.dashboard import _session_dep
from src.shared.models import AdminUser


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
    import src.admin.routes.dashboard as dash_routes

    dash_routes.DashboardService = lambda session: service_mock  # type: ignore[attr-defined,assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def test_dashboard_renders_counters(fake_admin_middleware_session: None) -> None:
    """Dashboard handler вызывает сервис и передаёт счётчики в шаблон."""
    service = MagicMock()
    service.get_counters = AsyncMock(return_value={"users": 10, "events": 5, "categories": 3, "predictions": 25})

    client = _client(service)
    response = client.get("/")

    assert response.status_code == 200
    service.get_counters.assert_awaited_once_with()

    content = response.text
    assert "10" in content
    assert "5" in content
    assert "3" in content
    assert "25" in content
    assert "TASK-024" not in content  # warning-текст удалён


def test_dashboard_with_zero_counters(fake_admin_middleware_session: None) -> None:
    """Dashboard корректно отображает нулевые значения."""
    service = MagicMock()
    service.get_counters = AsyncMock(return_value={"users": 0, "events": 0, "categories": 0, "predictions": 0})

    client = _client(service)
    response = client.get("/")

    assert response.status_code == 200
    content = response.text
    assert content.count(">0<") >= 4  # четыре нуля на странице
