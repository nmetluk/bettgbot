"""Тесты handler'ов раздела «Пользователи» (TASK-025)."""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.admin.routes.users import _session_dep as users_session_dep
from src.shared.models import AdminUser, Event, Outcome, Prediction, User


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    a.full_name = None
    return a


def _make_user(
    *,
    id: int = 42,
    tg_username: str = "alice",
    is_blocked: bool = False,
    phone: str = "+79991112233",
) -> MagicMock:
    u = MagicMock(spec=User)
    u.id = id
    u.tg_user_id = 100 + id
    u.phone = phone
    u.tg_username = tg_username
    u.first_name = "Alice"
    u.last_name = "Smith"
    u.is_blocked = is_blocked
    u.created_at = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    u.last_seen_at = datetime(2026, 5, 1, 18, 0, tzinfo=UTC)
    return u


def _make_prediction(*, id: int = 1, is_correct: bool | None = None) -> MagicMock:
    p = MagicMock(spec=Prediction)
    p.id = id
    p.user_id = 42
    p.event_id = 10
    p.outcome_id = 1
    p.is_correct = is_correct

    event = MagicMock(spec=Event)
    event.id = 10
    event.title = "Финал"
    event.is_archived = False
    event.is_published = True
    event.starts_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    p.event = event

    outcome = MagicMock(spec=Outcome)
    outcome.id = 1
    outcome.label = "Win"
    p.outcome = outcome
    return p


async def _bypass_session():
    yield MagicMock()


@pytest.fixture
def fake_admin_middleware_session():
    fake_admin = _make_admin()
    fake_session = MagicMock()

    async def _get(model, pk):
        return fake_admin

    fake_session.get = _get

    @asynccontextmanager
    async def _cm():
        yield fake_session

    maker = MagicMock()
    maker.side_effect = lambda: _cm()
    with patch("src.admin.auth.middleware.SessionLocal", maker):
        yield


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _client(
    *,
    user_service: MagicMock | None = None,
    prediction_service: MagicMock | None = None,
    stats_service: MagicMock | None = None,
) -> TestClient:
    app.dependency_overrides[current_admin] = lambda: _make_admin()
    app.dependency_overrides[users_session_dep] = _bypass_session
    import src.admin.routes.users as u_routes

    if user_service is not None:
        u_routes.UserService = lambda session, registry=None: user_service  # type: ignore[assignment]
    if prediction_service is not None:
        u_routes.PredictionService = lambda session: prediction_service  # type: ignore[assignment]
    if stats_service is not None:
        u_routes.StatsService = lambda session: stats_service  # type: ignore[assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


def _get_csrf(client: TestClient, url: str = "/login") -> str:
    """Получить CSRF token. По умолчанию через /login — public, не требует service-mock'ов."""
    response = client.get(url)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None, f"no csrf_token in {url} (status={response.status_code})"
    return match.group(1)


def test_unauthorized_redirects_to_login() -> None:
    client = TestClient(app, follow_redirects=False)
    response = client.get("/users")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_users_renders_table(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.list_admin_with_counts = AsyncMock(return_value=[(_make_user(), 7)])
    user_service.count_for_admin = AsyncMock(return_value=1)

    client = _client(user_service=user_service)
    response = client.get("/users")

    assert response.status_code == 200
    assert "Alice" in response.text
    assert "@alice" in response.text
    assert "<td>7</td>" in response.text


def test_list_users_with_query_filters_results(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.list_admin_with_counts = AsyncMock(
        return_value=[(_make_user(tg_username="bob"), 2)]
    )
    user_service.count_for_admin = AsyncMock(return_value=1)

    client = _client(user_service=user_service)
    response = client.get("/users?query=bob")

    assert response.status_code == 200
    user_service.list_admin_with_counts.assert_awaited_once()
    call_kwargs = user_service.list_admin_with_counts.await_args.kwargs
    assert call_kwargs["query"] == "bob"


def test_user_detail_renders_profile_and_predictions(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=_make_user(id=42))
    pred_service = MagicMock()
    pred_service.list_all_by_user_for_admin = AsyncMock(
        return_value=[_make_prediction(id=1, is_correct=True)]
    )
    stats_service = MagicMock()
    stats_service.user_stats = AsyncMock(return_value=(1, 1, 100.0))

    client = _client(
        user_service=user_service,
        prediction_service=pred_service,
        stats_service=stats_service,
    )
    response = client.get("/users/42")

    assert response.status_code == 200
    assert "Alice Smith" in response.text
    assert "Финал" in response.text
    assert "✅ сбылся" in response.text
    # Stats секция.
    assert "Статистика" in response.text


def test_user_detail_unknown_user_404(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=None)

    client = _client(user_service=user_service)
    response = client.get("/users/99999")

    assert response.status_code == 404


def test_block_user_redirects_with_success(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=_make_user(id=7, is_blocked=False))
    user_service.block = AsyncMock(return_value=None)

    client = _client(user_service=user_service)
    csrf_token = _get_csrf(client)
    response = client.post("/users/7/block", data={"csrf_token": csrf_token})

    assert response.status_code == 302
    assert response.headers["location"] == "/users/7?success=blocked"
    user_service.block.assert_awaited_once()


def test_unblock_user_redirects_with_success(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=_make_user(id=7, is_blocked=True))
    user_service.unblock = AsyncMock(return_value=None)

    client = _client(user_service=user_service)
    csrf_token = _get_csrf(client)
    response = client.post("/users/7/unblock", data={"csrf_token": csrf_token})

    assert response.status_code == 302
    assert response.headers["location"] == "/users/7?success=unblocked"


def test_user_detail_shows_block_button_when_active(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=_make_user(id=42, is_blocked=False))
    pred_service = MagicMock()
    pred_service.list_all_by_user_for_admin = AsyncMock(return_value=[])
    stats_service = MagicMock()
    stats_service.user_stats = AsyncMock(return_value=(0, 0, 0.0))

    client = _client(
        user_service=user_service,
        prediction_service=pred_service,
        stats_service=stats_service,
    )
    response = client.get("/users/42")

    assert response.status_code == 200
    assert "/users/42/block" in response.text
    assert "/users/42/unblock" not in response.text


def test_user_detail_shows_unblock_button_when_blocked(fake_admin_middleware_session) -> None:
    user_service = MagicMock()
    user_service.get_by_id = AsyncMock(return_value=_make_user(id=42, is_blocked=True))
    pred_service = MagicMock()
    pred_service.list_all_by_user_for_admin = AsyncMock(return_value=[])
    stats_service = MagicMock()
    stats_service.user_stats = AsyncMock(return_value=(0, 0, 0.0))

    client = _client(
        user_service=user_service,
        prediction_service=pred_service,
        stats_service=stats_service,
    )
    response = client.get("/users/42")

    assert response.status_code == 200
    assert "/users/42/unblock" in response.text
    assert '/users/42/block"' not in response.text  # точное окончание action attribute
