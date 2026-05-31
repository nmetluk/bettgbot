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
    from datetime import UTC, datetime

    from src.shared.services.dashboard import ActiveEventInfo, AuditLogInfo

    service = MagicMock()
    service.get_counters = AsyncMock(
        return_value={
            "users_total": 10,
            "users_active_30d": 5,
            "predictions_total": 25,
            "predictions_24h": 2,
            "events_total": 5,
            "events_published": 3,
            "events_archived": 1,
            "categories": 3,
            "categories_hidden": 0,
        }
    )
    service.get_active_events = AsyncMock(return_value=[])
    service.get_recent_audit_logs = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/")

    assert response.status_code == 200
    service.get_counters.assert_awaited_once_with()
    service.get_active_events.assert_awaited_once_with(limit=10)
    service.get_recent_audit_logs.assert_awaited_once_with(limit=8)

    content = response.text
    assert "10" in content  # users_total
    assert "25" in content  # predictions_total
    assert "5" in content  # events_total
    assert "3" in content  # categories
    assert "TASK-024" not in content  # warning-текст удалён


def test_dashboard_with_zero_counters(fake_admin_middleware_session: None) -> None:
    """Dashboard корректно отображает нулевые значения."""
    service = MagicMock()
    service.get_counters = AsyncMock(
        return_value={
            "users_total": 0,
            "users_active_30d": 0,
            "predictions_total": 0,
            "predictions_24h": 0,
            "events_total": 0,
            "events_published": 0,
            "events_archived": 0,
            "categories": 0,
            "categories_hidden": 0,
        }
    )
    service.get_active_events = AsyncMock(return_value=[])
    service.get_recent_audit_logs = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/")

    assert response.status_code == 200


def test_alpine_ui_store_registration_order(fake_admin_middleware_session: None) -> None:
    """Regression for TASK-090: ui.js (Alpine.store + alpine:init listener) MUST load before alpine-csp.

    If reversed, the 'alpine:init' event is missed (both defer), store never registers,
    and all theme/density/rail/accent controls are dead (as observed in prod audit).
    """
    from src.shared.services.dashboard import ActiveEventInfo, AuditLogInfo

    service = MagicMock()
    service.get_counters = AsyncMock(
        return_value={
            "users_total": 0,
            "users_active_30d": 0,
            "predictions_total": 0,
            "predictions_24h": 0,
            "events_total": 0,
            "events_published": 0,
            "events_archived": 0,
            "categories": 0,
            "categories_hidden": 0,
        }
    )
    service.get_active_events = AsyncMock(return_value=[])
    service.get_recent_audit_logs = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/")
    html = response.text

    assert response.status_code == 200

    # Find positions of the two critical scripts (TASK-094: allow ?v= cache-busting param)
    ui_js_pos = html.find('src="/static/js/ui.js')
    alpine_pos = html.find('src="/static/vendor/alpine-csp-3.14.1.min.js"')

    assert ui_js_pos != -1, "ui.js script tag missing"
    assert alpine_pos != -1, "alpine-csp script tag missing"
    assert ui_js_pos < alpine_pos, (
        "ui.js must appear BEFORE alpine-csp in the document so the alpine:init listener "
        "is registered in time (TASK-090 / TASK-057 CSP risk)"
    )
    content = response.text
    # Проверяем, что нули есть на странице (как минимум в нескольких местах)
    assert "0" in content
    # Проверяем отсутствие warning-текста
    assert "TASK-024" not in content
