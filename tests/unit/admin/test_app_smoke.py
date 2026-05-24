"""Smoke-тесты FastAPI-приложения админки (TASK-019)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from src.admin.app import app


def test_app_builds_without_error() -> None:
    assert app.title == "Betting Bot Admin"


def test_healthz_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_form_renders() -> None:
    client = TestClient(app)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Вход" in response.text
    assert 'name="login"' in response.text
    assert 'name="password"' in response.text


def test_dashboard_redirects_unauthenticated_to_login() -> None:
    # После TASK-020 / защищён RequireAdminMiddleware: без cookie → 302 на /login.
    client = TestClient(app, follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
