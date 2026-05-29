"""Тесты analytics-handler'а (TASK-059)."""

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
from src.admin.routes.analytics import _session_dep
from src.shared.models import AdminUser
from src.shared.services import (
    AnalyticsDayRow,
    AnalyticsFunnelMetrics,
    AnalyticsTopEventRow,
    CategoryAccuracyRow,
)


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
    import src.admin.routes.analytics as analytics_routes

    analytics_routes.StatsService = lambda session: service_mock  # type: ignore[attr-defined,assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


@pytest.fixture(autouse=True)
def _clear_overrides() -> Generator[None, None, None]:
    yield
    app.dependency_overrides.clear()


def test_analytics_renders_all_sections(fake_admin_middleware_session: None) -> None:
    """Handler вызывает все 4 метода сервиса и рендерит секции."""
    service = MagicMock()
    service.daily_prediction_counts = AsyncMock(
        return_value=[
            AnalyticsDayRow(date="2026-05-28", count=5),
            AnalyticsDayRow(date="2026-05-29", count=10),
        ]
    )
    service.category_accuracy = AsyncMock(
        return_value=[
            CategoryAccuracyRow(
                category_id=1,
                category_name="Football",
                category_slug="football",
                correct=8,
                resolved=10,
                accuracy=80.0,
            )
        ]
    )
    service.funnel_metrics = AsyncMock(
        return_value=AnalyticsFunnelMetrics(
            total_users=100,
            users_with_predictions=40,
            conversion_percent=40.0,
        )
    )
    service.top_events = AsyncMock(
        return_value=[
            AnalyticsTopEventRow(
                event_id=1,
                event_title="Big Match",
                category_slug="football",
                prediction_count=25,
            )
        ]
    )

    client = _client(service)
    response = client.get("/analytics")

    assert response.status_code == 200

    service.daily_prediction_counts.assert_awaited_once_with(days=30)
    service.category_accuracy.assert_awaited_once()
    service.funnel_metrics.assert_awaited_once()
    service.top_events.assert_awaited_once_with(limit=10)

    content = response.text
    # Проверим KPI воронки
    assert "100" in content  # total_users
    assert "40" in content  # users_with_predictions
    assert "40.0%" in content  # conversion
    # Проверим категорию
    assert "Football" in content
    assert "80.0%" in content
    # Проверим топ-события
    assert "Big Match" in content
    assert "25" in content  # prediction_count


def test_analytics_empty_category_accuracy(fake_admin_middleware_session: None) -> None:
    """Handler отображает пустое состояние для категорий без данных."""
    service = MagicMock()
    service.daily_prediction_counts = AsyncMock(return_value=[])
    service.category_accuracy = AsyncMock(return_value=[])
    service.funnel_metrics = AsyncMock(
        return_value=AnalyticsFunnelMetrics(
            total_users=0,
            users_with_predictions=0,
            conversion_percent=0.0,
        )
    )
    service.top_events = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/analytics")

    assert response.status_code == 200
    content = response.text
    # Проверим пустое состояние категорий
    assert "нет данных" in content.lower() or "нет разрешённых" in content.lower()


def test_analytics_renders_chart_script(fake_admin_middleware_session: None) -> None:
    """Handler рендерит CSP-совместимые скрипты: внешний analytics.js и JSON-блок данных."""
    service = MagicMock()
    service.daily_prediction_counts = AsyncMock(
        return_value=[AnalyticsDayRow(date="2026-05-29", count=42)]
    )
    service.category_accuracy = AsyncMock(
        return_value=[
            CategoryAccuracyRow(
                category_id=1,
                category_name="Test",
                category_slug="test",
                correct=3,
                resolved=5,
                accuracy=60.0,
            )
        ]
    )
    service.funnel_metrics = AsyncMock(
        return_value=AnalyticsFunnelMetrics(
            total_users=10,
            users_with_predictions=5,
            conversion_percent=50.0,
        )
    )
    service.top_events = AsyncMock(return_value=[])

    client = _client(service)
    response = client.get("/analytics")

    assert response.status_code == 200
    content = response.text
    # Chart.js через CDN
    assert "chart.js" in content.lower()
    # Внешний скрипт инициализации (CSP-совместимый)
    assert "/static/js/analytics.js" in content
    # JSON-блок с данными (CSP-совместимый, не исполняемый)
    assert 'id="analytics-data"' in content
    assert 'type="application/json"' in content
    assert '"daily_counts"' in content
    assert '"category_accuracy"' in content
    # Canvas элементы для графиков
    assert "dailyChart" in content
    assert "categoryChart" in content
