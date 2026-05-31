"""Тесты handler'ов аудит-журнала (TASK-026)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.admin.routes.audit import _session_dep as audit_session_dep
from src.shared.models import AdminUser, AuditLog


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    a.full_name = None
    return a


def _make_audit_entry(
    *, id: int = 1, action: str = "event.create", admin_login: str = "alice"
) -> MagicMock:
    e = MagicMock(spec=AuditLog)
    e.id = id
    e.admin_id = 99
    e.action = action
    e.payload = {"event_id": 5, "title": "Финал"}
    e.created_at = datetime(2026, 5, 24, 14, 0, 0, tzinfo=UTC)

    admin_obj = MagicMock(spec=AdminUser)
    admin_obj.id = 99
    admin_obj.login = admin_login
    admin_obj.full_name = "Alice"
    e.admin = admin_obj
    return e


def _make_admin_for_dropdown(*, id: int = 99, login: str = "alice") -> MagicMock:
    a = MagicMock(spec=AdminUser)
    a.id = id
    a.login = login
    a.full_name = "Alice"
    return a


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


_SENTINEL_NOT_FOUND = object()


def _client(
    *,
    audit_service: MagicMock | None = None,
    admin_repo: MagicMock | None = None,
    session_get_returns: object | None | type[object] = _SENTINEL_NOT_FOUND,
) -> TestClient:
    """`session_get_returns` — fake return value for `session.get(AuditLog, id)`.

    Sentinel default — для тестов без details/collapse (любое значение). None —
    эмулирует «не найдено» (handler вернёт 404).
    """
    app.dependency_overrides[current_admin] = lambda: _make_admin()

    if session_get_returns is _SENTINEL_NOT_FOUND:

        async def _yield_session_default() -> object:
            yield MagicMock()

        app.dependency_overrides[audit_session_dep] = _yield_session_default
    else:
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=session_get_returns)

        async def _yield_session() -> object:
            yield mock_session

        app.dependency_overrides[audit_session_dep] = _yield_session

    import src.admin.routes.audit as a_routes

    if audit_service is not None:
        a_routes.AuditService = lambda session: audit_service  # type: ignore[assignment]
    if admin_repo is not None:
        a_routes.AdminUserRepository = lambda session: admin_repo  # type: ignore[assignment]

    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


def test_unauthorized_redirects_to_login() -> None:
    client = TestClient(app, follow_redirects=False)
    response = client.get("/audit")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_audit_renders_with_filters(fake_admin_middleware_session) -> None:
    audit_service = MagicMock()
    audit_service.list = AsyncMock(return_value=[_make_audit_entry(action="event.create")])
    audit_service.count = AsyncMock(return_value=1)
    admin_repo = MagicMock()
    admin_repo.list_all = AsyncMock(return_value=[_make_admin_for_dropdown()])

    client = _client(audit_service=audit_service, admin_repo=admin_repo)
    response = client.get("/audit")

    assert response.status_code == 200
    assert "Аудит-лог" in response.text
    assert 'name="admin_id"' in response.text
    assert 'name="action"' in response.text
    assert "event.create" in response.text


def test_list_audit_with_admin_id_filter(fake_admin_middleware_session) -> None:
    audit_service = MagicMock()
    audit_service.list = AsyncMock(return_value=[])
    audit_service.count = AsyncMock(return_value=0)
    admin_repo = MagicMock()
    admin_repo.list_all = AsyncMock(return_value=[])

    client = _client(audit_service=audit_service, admin_repo=admin_repo)
    response = client.get("/audit?admin_id=7")

    assert response.status_code == 200
    call_kwargs = audit_service.list.await_args.kwargs
    assert call_kwargs["admin_id"] == 7


def test_list_audit_with_action_filter(fake_admin_middleware_session) -> None:
    audit_service = MagicMock()
    audit_service.list = AsyncMock(return_value=[])
    audit_service.count = AsyncMock(return_value=0)
    admin_repo = MagicMock()
    admin_repo.list_all = AsyncMock(return_value=[])

    client = _client(audit_service=audit_service, admin_repo=admin_repo)
    response = client.get("/audit?action=event.create")

    assert response.status_code == 200
    call_kwargs = audit_service.list.await_args.kwargs
    assert call_kwargs["action"] == "event.create"


def test_details_fragment_returns_pretty_json(fake_admin_middleware_session) -> None:
    entry = _make_audit_entry(id=42)
    client = _client(session_get_returns=entry)
    response = client.get("/audit/42/details")

    assert response.status_code == 200
    assert "Свернуть" in response.text
    # JSON pretty с indent=2; Jinja HTML-escape'ит кавычки → &#34;.
    assert "event_id" in response.text
    assert "title" in response.text
    assert "Финал" in response.text


def test_details_fragment_unknown_id_404(fake_admin_middleware_session) -> None:
    client = _client(session_get_returns=None)
    response = client.get("/audit/99999/details")

    assert response.status_code == 404


def test_details_collapse_returns_preview_fragment(fake_admin_middleware_session) -> None:
    entry = _make_audit_entry(id=42)
    client = _client(session_get_returns=entry)
    response = client.get("/audit/42/details/collapse")

    assert response.status_code == 200
    # Preview-fragment — кнопка с hx-get на /details (раскрыть), не «Свернуть».
    assert "Свернуть" not in response.text
    assert 'hx-get="/audit/42/details"' in response.text


def test_audit_list_rows_have_matching_wrapper_divs_for_htmx_details(
    fake_admin_middleware_session,
) -> None:
    """Regression for TASK-091: each audit row must be wrapped in <div id="audit-row-{{id}}">

    The hx-target="#audit-row-{{id}}" on the expand button (and in _details/_preview fragments)
    had no matching element in the initial DOM → HTMX swap never happened.
    """
    audit_service = MagicMock()
    audit_service.list = AsyncMock(return_value=[_make_audit_entry(id=7), _make_audit_entry(id=42)])
    audit_service.count = AsyncMock(return_value=2)
    admin_repo = MagicMock()
    admin_repo.list_all = AsyncMock(return_value=[])

    client = _client(audit_service=audit_service, admin_repo=admin_repo)
    response = client.get("/audit")

    assert response.status_code == 200
    html = response.text

    # Both rows must have the wrapper div that the hx-target points to
    assert 'id="audit-row-7"' in html
    assert 'id="audit-row-42"' in html
    # And the button must still target it (defensive)
    assert 'hx-target="#audit-row-7"' in html
    assert 'hx-target="#audit-row-42"' in html
