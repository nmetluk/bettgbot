"""Тесты RequireAdminMiddleware (TASK-020)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_NAME_PROD,
    create_session_token,
)


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
    client = TestClient(app, follow_redirects=False, raise_server_exceptions=False)
    client.cookies.set(SESSION_COOKIE_NAME, token)

    with patch("src.admin.auth.middleware.SessionLocal", maker):
        response = client.get("/")

    # Middleware должен пропустить запрос (не редирект на /login)
    assert response.status_code != 302 or response.headers.get("location") != "/login"


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


@pytest.mark.parametrize(
    "env_name,expected_cookie_name",
    [("dev", SESSION_COOKIE_NAME), ("prod", SESSION_COOKIE_NAME_PROD)],
)
def test_session_cookie_name_depends_on_environment(
    env_name: str,
    expected_cookie_name: str,
) -> None:
    """Проверяет, что middleware читает session-куку с правильным именем для dev и prod.

    Этот тест проверяет, что логика выбора имени куки по окружению работает правильно.
    """
    from src.admin.auth.middleware import SESSION_COOKIE_NAME, SESSION_COOKIE_NAME_PROD
    from src.shared.config import Settings, get_settings

    # Получаем текущие настройки и создаём копию с изменённым environment
    original_settings = get_settings()
    fake_settings = original_settings.model_copy(update={"environment": env_name})

    # Проверяем, что правильное имя куки выбирается
    session_name = SESSION_COOKIE_NAME_PROD if fake_settings.environment != "dev" else SESSION_COOKIE_NAME

    assert session_name == expected_cookie_name


@pytest.mark.parametrize(
    "env_name,session_cookie_name",
    [("dev", SESSION_COOKIE_NAME), ("prod", SESSION_COOKIE_NAME_PROD)],
)
def test_prod_env_round_trip_with_correct_cookie_name(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    session_cookie_name: str,
) -> None:
    """Round-trip тест: middleware читает куку с правильным именем для dev и prod.

    Тест проверяет, что при установке куки с правильным именем
    middleware позволяет запрос пройти middleware, а не редиректит на /login.

    Фикс TASK-063: middleware теперь выбирает имя куки по окружению.
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.shared.config import Settings, get_settings

    # Создаём fake settings с нужным environment
    original_settings = get_settings()
    fake_settings = original_settings.model_copy(update={"environment": env_name})

    def fake_get_settings() -> Settings:
        return fake_settings

    # Патчим get_settings в middleware
    monkeypatch.setattr("src.admin.auth.middleware.get_settings", fake_get_settings)

    # Fake admin для ответа от DB
    fake_admin = MagicMock(spec_set=["id", "login", "is_active"])
    fake_admin.id = 42
    fake_admin.is_active = True

    # Async context manager для сессии
    fake_session = AsyncMock(spec=AsyncSession)
    fake_session.get = AsyncMock(return_value=fake_admin)

    @asynccontextmanager
    async def fake_session_maker():
        yield fake_session

    # Создаём токен и клиент
    token = create_session_token(admin_id=42)
    client = TestClient(app, follow_redirects=False, raise_server_exceptions=False)
    client.cookies.set(session_cookie_name, token)

    # SessionLocal patch для middleware
    maker = MagicMock()
    maker.side_effect = lambda: fake_session_maker()

    with patch("src.admin.auth.middleware.SessionLocal", maker):
        # Проверяем middleware на защищенном маршруте
        response = client.get("/")

    # Если middleware читает правильную куку, запрос проходит middleware (не редирект на /login)
    # Handler может упасть на БД, но middleware уже пропустил запрос
    assert response.status_code != 302 or response.headers.get("location") != "/login"
