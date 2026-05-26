"""Тесты HTMX-handler'ов исходов (TASK-023)."""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.admin.routes.outcomes import _session_dep as outcomes_session_dep
from src.shared.exceptions import OutcomeInUseError, OutcomeNotForEventError, OutcomeNotFoundError
from src.shared.models import AdminUser, Event, Outcome


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    a.full_name = None
    return a


def _make_outcome(*, id: int = 1, label: str = "Победа", sort_order: int = 0) -> MagicMock:
    o = MagicMock(spec=Outcome)
    o.id = id
    o.label = label
    o.sort_order = sort_order
    return o


def _make_event_with_outcomes(
    *, id: int = 10, outcomes: list[MagicMock] | None = None
) -> MagicMock:
    e = MagicMock(spec=Event)
    e.id = id
    e.outcomes = outcomes if outcomes is not None else []
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


def _client(*, event_service: MagicMock | None = None) -> TestClient:
    app.dependency_overrides[current_admin] = lambda: _make_admin()
    app.dependency_overrides[outcomes_session_dep] = _bypass_session
    import src.admin.routes.outcomes as out_routes

    if event_service is not None:
        out_routes.EventService = lambda session: event_service  # type: ignore[assignment]
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
    response = client.get("/events/10/outcomes")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_fragment_returns_outcomes_html(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    outcomes = [_make_outcome(id=1, label="Победа"), _make_outcome(id=2, label="Ничья")]
    ev_service.get_event = AsyncMock(
        return_value=_make_event_with_outcomes(id=10, outcomes=outcomes)
    )

    client = _client(event_service=ev_service)
    response = client.get("/events/10/outcomes")

    assert response.status_code == 200
    assert 'id="outcomes-container"' in response.text
    assert "Победа" in response.text
    assert "Ничья" in response.text


def test_list_fragment_empty_shows_hint(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.get_event = AsyncMock(return_value=_make_event_with_outcomes(id=10, outcomes=[]))

    client = _client(event_service=ev_service)
    response = client.get("/events/10/outcomes")

    assert response.status_code == 200
    assert "Исходов ещё нет" in response.text


def test_new_form_fragment_returns_form_html(fake_admin_middleware_session) -> None:
    client = _client()
    response = client.get("/events/10/outcomes/new")

    assert response.status_code == 200
    assert 'hx-post="/events/10/outcomes"' in response.text
    assert "Новый исход" in response.text


def test_create_outcome_returns_updated_list(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.add_outcome = AsyncMock(return_value=_make_outcome(id=3, label="Created"))
    ev_service.get_event = AsyncMock(
        return_value=_make_event_with_outcomes(
            id=10, outcomes=[_make_outcome(id=3, label="Created")]
        )
    )

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/10/outcomes/new")
    response = client.post(
        "/events/10/outcomes",
        data={"csrf_token": csrf_token, "label": "Created", "sort_order": 0},
    )

    assert response.status_code == 200
    assert "Created" in response.text
    assert 'id="outcomes-container"' in response.text


def test_edit_form_fragment_pre_fills_values(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    outcome = _make_outcome(id=5, label="Existing", sort_order=10)
    ev_service.get_event = AsyncMock(
        return_value=_make_event_with_outcomes(id=10, outcomes=[outcome])
    )

    client = _client(event_service=ev_service)
    response = client.get("/events/10/outcomes/5/edit")

    assert response.status_code == 200
    assert 'value="Existing"' in response.text
    assert 'value="10"' in response.text
    assert "Редактирование исхода #5" in response.text


def test_update_outcome_returns_updated_list(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.update_outcome = AsyncMock(return_value=None)
    ev_service.get_event = AsyncMock(
        return_value=_make_event_with_outcomes(
            id=10, outcomes=[_make_outcome(id=5, label="Updated")]
        )
    )

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/10/outcomes/new")
    response = client.post(
        "/events/10/outcomes/5",
        data={"csrf_token": csrf_token, "label": "Updated", "sort_order": 0},
    )

    # Проверяем что update_outcome был вызван с правильным event_id
    ev_service.update_outcome.assert_called_once()
    call_kwargs = ev_service.update_outcome.call_args.kwargs
    assert call_kwargs["event_id"] == 10
    assert call_kwargs["outcome_id"] == 5

    assert response.status_code == 200
    assert "Updated" in response.text


def test_delete_outcome_success_returns_updated_list(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.delete_outcome = AsyncMock(return_value=None)
    ev_service.get_event = AsyncMock(return_value=_make_event_with_outcomes(id=10, outcomes=[]))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/10/outcomes/new")
    response = client.post(
        "/events/10/outcomes/5/delete",
        data={"csrf_token": csrf_token},
    )

    # Проверяем что delete_outcome был вызван с правильным event_id
    ev_service.delete_outcome.assert_called_once()
    call_kwargs = ev_service.delete_outcome.call_args.kwargs
    assert call_kwargs["event_id"] == 10
    assert call_kwargs["outcome_id"] == 5

    assert response.status_code == 200
    assert "Исходов ещё нет" in response.text


def test_delete_outcome_in_use_returns_409_with_alert(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.delete_outcome = AsyncMock(side_effect=OutcomeInUseError("has predictions"))
    ev_service.get_event = AsyncMock(
        return_value=_make_event_with_outcomes(
            id=10, outcomes=[_make_outcome(id=5, label="Has predictions")]
        )
    )

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/10/outcomes/new")
    response = client.post(
        "/events/10/outcomes/5/delete",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 409
    assert "Нельзя удалить" in response.text
    assert "alert-warning" in response.text


def test_delete_unknown_outcome_404(fake_admin_middleware_session) -> None:
    ev_service = MagicMock()
    ev_service.delete_outcome = AsyncMock(
        side_effect=OutcomeNotForEventError(event_id=10, outcome_id=999)
    )
    ev_service.get_event = AsyncMock(return_value=_make_event_with_outcomes(id=10, outcomes=[]))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/10/outcomes/new")
    response = client.post(
        "/events/10/outcomes/999/delete",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 404


def test_update_outcome_from_wrong_event_returns_404(fake_admin_middleware_session) -> None:
    """POST /events/1/outcomes/999 где 999 принадлежит event 2 → 404."""
    ev_service = MagicMock()
    ev_service.update_outcome = AsyncMock(
        side_effect=OutcomeNotForEventError(event_id=1, outcome_id=999)
    )
    ev_service.get_event = AsyncMock(return_value=_make_event_with_outcomes(id=1, outcomes=[]))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/1/outcomes/new")
    response = client.post(
        "/events/1/outcomes/999",
        data={"csrf_token": csrf_token, "label": "Hacked", "sort_order": 0},
    )

    assert response.status_code == 404


def test_delete_outcome_from_wrong_event_returns_404(fake_admin_middleware_session) -> None:
    """POST /events/1/outcomes/999/delete где 999 принадлежит event 2 → 404."""
    ev_service = MagicMock()
    ev_service.delete_outcome = AsyncMock(
        side_effect=OutcomeNotForEventError(event_id=1, outcome_id=999)
    )
    ev_service.get_event = AsyncMock(return_value=_make_event_with_outcomes(id=1, outcomes=[]))

    client = _client(event_service=ev_service)
    csrf_token = _get_csrf(client, "/events/1/outcomes/new")
    response = client.post(
        "/events/1/outcomes/999/delete",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 404
