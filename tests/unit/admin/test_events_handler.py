"""Тесты handler'ов событий админки (TASK-022)."""

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
from src.admin.routes.events import _session_dep as events_session_dep
from src.shared.exceptions import (
    EventAlreadyHasResultError,
    EventNotEnoughOutcomesError,
    EventNotFoundError,
    OutcomeNotForEventError,
)
from src.shared.models import AdminUser, Category, Event


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    a.full_name = None
    return a


def _make_category(*, id: int = 1, name: str = "Спорт") -> MagicMock:
    c = MagicMock(spec=Category)
    c.id = id
    c.name = name
    c.slug = f"cat-{id}"
    c.sort_order = 0
    c.is_active = True
    return c


def _make_event(*, id: int = 10, title: str = "Финал") -> MagicMock:
    e = MagicMock(spec=Event)
    e.id = id
    e.title = title
    e.description = None
    e.category_id = 1
    e.category = _make_category()
    e.starts_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    e.predictions_close_at = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
    e.is_published = False
    e.is_archived = False
    e.metadata_ = {}
    return e


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
    event_service: MagicMock | None = None,
    category_service: MagicMock | None = None,
) -> TestClient:
    app.dependency_overrides[current_admin] = lambda: _make_admin()
    app.dependency_overrides[events_session_dep] = _bypass_session
    import src.admin.routes.events as ev_routes

    if event_service is not None:
        ev_routes.EventService = lambda session: event_service  # type: ignore[assignment]
    if category_service is not None:
        ev_routes.CategoryService = lambda session: category_service  # type: ignore[assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


def _get_csrf(client: TestClient, url: str) -> str:
    response = client.get(url)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None, f"no csrf_token in {url} (status={response.status_code})"
    return match.group(1)


def test_unauthorized_redirects_to_login() -> None:
    client = TestClient(app, follow_redirects=False)
    response = client.get("/events")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_events_renders_with_filters(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.list_admin_with_counts = AsyncMock(return_value=[(_make_event(title="Финал"), 5)])
    ev_service.count_admin = AsyncMock(return_value=1)
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 1)])

    client = _client(event_service=ev_service, category_service=cat_service)
    response = client.get("/events")

    assert response.status_code == 200
    assert "Финал" in response.text
    assert 'name="status"' in response.text
    assert 'name="period"' in response.text


def test_new_form_renders_with_categories(fake_admin_middleware_session) -> None:
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(name="Футбол"), 0)])

    client = _client(category_service=cat_service)
    response = client.get("/events/new")

    assert response.status_code == 200
    assert "Новое событие" in response.text
    assert "Футбол" in response.text


def test_create_event_redirects_to_edit(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.create_event = AsyncMock(return_value=_make_event(id=99))
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events",
        data={
            "csrf_token": csrf_token,
            "title": "Match",
            "description": "",
            "category_id": 1,
            "starts_at": "2026-06-01T12:00",
            "predictions_close_at": "2026-06-01T11:00",
            "metadata": "{}",
        },
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/events/99"


def test_create_event_invalid_metadata_renders_error(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events",
        data={
            "csrf_token": csrf_token,
            "title": "Match",
            "description": "",
            "category_id": 1,
            "starts_at": "2026-06-01T12:00",
            "predictions_close_at": "2026-06-01T11:00",
            "metadata": "{not-json",
        },
    )
    assert response.status_code == 400
    assert "Неверный формат" in response.text


def test_edit_form_renders_with_tabs(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.get_event = AsyncMock(return_value=_make_event(id=7, title="Existing"))
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    response = client.get("/events/7")

    assert response.status_code == 200
    assert "Existing" in response.text
    assert "nav-tabs" in response.text
    # Исходы и Результат вкладки — обе после TASK-024 активны/conditional.
    assert "Исходы" in response.text
    assert "Результат" in response.text


def test_publish_event_success_redirects(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.publish_event = AsyncMock(return_value=None)

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")  # любой GET для csrf
    response = client.post("/events/5/publish", data={"csrf_token": csrf_token})
    assert response.status_code == 302
    assert response.headers["location"] == "/events/5"


def test_publish_event_not_enough_outcomes_redirects_with_error_param(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    ev_service.publish_event = AsyncMock(side_effect=EventNotEnoughOutcomesError("nope"))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post("/events/5/publish", data={"csrf_token": csrf_token})
    assert response.status_code == 302
    assert "error=not_enough_outcomes" in response.headers["location"]


def test_unpublish_event_success_redirects(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.unpublish_event = AsyncMock(return_value=None)

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post("/events/5/unpublish", data={"csrf_token": csrf_token})
    assert response.status_code == 302
    assert response.headers["location"] == "/events/5"


# --- TASK-024: set_result + Результат tab ---


def _make_outcome_simple(*, id: int = 1, label: str = "Win") -> MagicMock:
    o = MagicMock()
    o.id = id
    o.label = label
    o.sort_order = 0
    return o


def _make_published_past_event(
    *,
    id: int = 7,
    outcomes: list[MagicMock] | None = None,
    result_outcome_id: int | None = None,
    archived_at: datetime | None = None,
) -> MagicMock:
    e = MagicMock(spec=Event)
    e.id = id
    e.title = "Past"
    e.description = None
    e.category_id = 1
    e.category = _make_category()
    e.starts_at = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)
    # В прошлом — позволяет вкладке Результат быть активной.
    e.predictions_close_at = datetime(2026, 5, 20, 11, 0, tzinfo=UTC)
    e.is_published = True
    e.is_archived = result_outcome_id is not None
    e.metadata_ = {}
    e.outcomes = outcomes or [
        _make_outcome_simple(id=1, label="A"),
        _make_outcome_simple(id=2, label="B"),
    ]
    e.result_outcome_id = result_outcome_id
    e.archived_at = archived_at
    return e


def test_set_result_success_redirects_with_success_flash(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    ev_service.set_result = AsyncMock(return_value=3)

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events/5/result",
        data={"csrf_token": csrf_token, "outcome_id": 1},
    )
    assert response.status_code == 302
    loc = response.headers["location"]
    assert "tab=result" in loc
    assert "success=result_set" in loc
    assert "marked=3" in loc


def test_set_result_already_set_redirects_with_error(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    ev_service.set_result = AsyncMock(side_effect=EventAlreadyHasResultError("dup"))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events/5/result",
        data={"csrf_token": csrf_token, "outcome_id": 1},
    )
    assert response.status_code == 302
    assert "error=already_set" in response.headers["location"]


def test_set_result_outcome_not_for_event_redirects_with_error(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    ev_service.set_result = AsyncMock(
        side_effect=OutcomeNotForEventError(event_id=5, outcome_id=99)
    )

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events/5/result",
        data={"csrf_token": csrf_token, "outcome_id": 99},
    )
    assert response.status_code == 302
    assert "error=outcome_not_for_event" in response.headers["location"]


def test_set_result_unknown_event_404(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.set_result = AsyncMock(side_effect=EventNotFoundError("no"))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/new")
    response = client.post(
        "/events/999/result",
        data={"csrf_token": csrf_token, "outcome_id": 1},
    )
    assert response.status_code == 404


def test_edit_form_result_tab_visible_when_published_and_deadline_passed(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    ev_service.get_event = AsyncMock(return_value=_make_published_past_event(id=7))
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    response = client.get("/events/7?tab=result")

    assert response.status_code == 200
    assert "Фиксация итога" in response.text
    # Радио-кнопки для каждого исхода.
    assert 'name="outcome_id"' in response.text
    assert "🏁 Зафиксировать" in response.text


def test_edit_form_result_tab_disabled_when_not_published(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    event = _make_published_past_event(id=7)
    event.is_published = False
    ev_service.get_event = AsyncMock(return_value=event)
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    response = client.get("/events/7?tab=data")

    assert response.status_code == 200
    # Вкладка «Результат» рендерится с classes disabled + aria-disabled.
    assert 'aria-disabled="true"' in response.text
    assert "Доступно после дедлайна" in response.text


def test_edit_form_result_tab_shows_readonly_when_result_set(
    fake_admin_middleware_session,
) -> None:
    ev_service = MagicMock()
    event = _make_published_past_event(
        id=7,
        result_outcome_id=1,
        archived_at=datetime(2026, 5, 21, 18, 0, tzinfo=UTC),
    )
    ev_service.get_event = AsyncMock(return_value=event)
    cat_service = MagicMock()
    cat_service.list_all_with_counts = AsyncMock(return_value=[(_make_category(), 0)])

    client = _client(event_service=ev_service, category_service=cat_service)
    response = client.get("/events/7?tab=result")

    assert response.status_code == 200
    assert "🏁 Итог:" in response.text
    # Read-only — нет формы / radio-кнопок.
    assert 'name="outcome_id"' not in response.text
    assert "Зафиксирован:" in response.text
