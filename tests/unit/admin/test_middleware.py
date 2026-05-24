"""Тесты RequireAdminMiddleware (TASK-020)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token


def test_unauthenticated_redirects_to_login() -> None:
    client = TestClient(app, follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_healthz_passes_through_without_cookie() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_form_public_without_cookie() -> None:
    client = TestClient(app)
    response = client.get("/login")
    assert response.status_code == 200


def test_static_file_public_without_cookie() -> None:
    client = TestClient(app)
    response = client.get("/static/css/volt.css")
    assert response.status_code == 200


def test_valid_cookie_passes_through_with_mocked_session_maker() -> None:
    # Подменяем SessionLocal в middleware: возвращаем session.get → fake admin.
    fake_admin = MagicMock()
    fake_admin.id = 42
    fake_admin.is_active = True

    fake_session = MagicMock()

    async def _get(model, pk):
        return fake_admin

    fake_session.get = _get

    @asynccontextmanager
    async def fake_session_maker():
        yield fake_session

    maker = MagicMock()
    maker.side_effect = lambda: fake_session_maker()

    token = create_session_token(admin_id=42)
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, token)

    with patch("src.admin.auth.middleware.SessionLocal", maker):
        response = client.get("/")

    assert response.status_code == 200
    assert "Дашборд" in response.text


def test_stale_cookie_admin_deleted_redirects_and_clears_cookie() -> None:
    fake_session = MagicMock()

    async def _get(model, pk):
        return None  # admin удалён после issue cookie

    fake_session.get = _get

    @asynccontextmanager
    async def fake_session_maker():
        yield fake_session

    maker = MagicMock()
    maker.side_effect = lambda: fake_session_maker()

    token = create_session_token(admin_id=999)
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, token)

    with patch("src.admin.auth.middleware.SessionLocal", maker):
        response = client.get("/")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    set_cookie_headers = response.headers.get_list("set-cookie")
    # Cookie должен быть очищен.
    assert any(SESSION_COOKIE_NAME in h for h in set_cookie_headers)
