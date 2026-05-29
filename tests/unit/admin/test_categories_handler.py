"""Тесты CRUD-handler'ов категорий (TASK-021).

Подменяем CategoryService на mock + dependency_overrides для current_admin / session.
Для прохождения RequireAdminMiddleware:
- ставим валидный signed-cookie через `create_session_token`;
- патчим `src.admin.auth.middleware.SessionLocal`, чтобы `session.get(AdminUser, id)`
  вернул fake admin.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.admin.routes.categories import _session_dep
from src.shared.exceptions import (
    CategoryHasEventsError,
    CategorySlugConflictError,
)
from src.shared.models import AdminUser, Category


def _make_admin() -> AdminUser:
    a = MagicMock(spec=AdminUser)
    a.id = 1
    a.login = "admin"
    a.is_active = True
    return a


async def _bypass_session():
    yield MagicMock()


@pytest.fixture
def fake_admin_middleware_session():
    """Патчит middleware'овский SessionLocal так, чтобы вернуть fake admin."""
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


def _client(service_mock: MagicMock) -> TestClient:
    app.dependency_overrides[current_admin] = lambda: _make_admin()
    app.dependency_overrides[_session_dep] = _bypass_session
    import src.admin.routes.categories as cat_routes

    cat_routes.CategoryService = lambda session: service_mock  # type: ignore[assignment]
    client = TestClient(app, follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(admin_id=1))
    return client


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _get_csrf(client: TestClient, url: str) -> tuple[str, dict[str, str]]:
    response = client.get(url)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None, f"no csrf_token in {url}"
    return match.group(1), dict(response.cookies)


def _make_category(
    *, id: int = 1, name: str = "Football", slug: str = "football", is_active: bool = True
) -> MagicMock:
    cat = MagicMock(spec=Category)
    cat.id = id
    cat.name = name
    cat.slug = slug
    cat.sort_order = 0
    cat.is_active = is_active
    return cat


def test_unauthorized_redirects_to_login() -> None:
    # Без override current_admin middleware видит отсутствие cookie → 302 /login.
    client = TestClient(app, follow_redirects=False)
    response = client.get("/categories")
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_list_categories_renders(fake_admin_middleware_session) -> None:
    service = MagicMock()
    service.list_all_with_counts = AsyncMock(return_value=[(_make_category(name="Спорт"), 5)])

    client = _client(service)
    response = client.get("/categories")

    assert response.status_code == 200
    assert "Категории" in response.text
    assert "Спорт" in response.text
    assert "pv-c-num" in response.text
    assert "5</td>" in response.text


def test_new_form_renders_with_csrf(fake_admin_middleware_session) -> None:
    service = MagicMock()
    client = _client(service)
    response = client.get("/categories/new")
    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert "Новая категория" in response.text


def test_create_category_redirects_on_success(fake_admin_middleware_session) -> None:
    service = MagicMock()
    service.create_category = AsyncMock(return_value=_make_category(id=42))

    client = _client(service)
    csrf_token, _ = _get_csrf(client, "/categories/new")
    response = client.post(
        "/categories",
        data={
            "csrf_token": csrf_token,
            "name": "X",
            "slug": "x-1",
            "sort_order": 0,
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/categories"


def test_create_category_409_on_slug_conflict(fake_admin_middleware_session) -> None:
    service = MagicMock()
    service.create_category = AsyncMock(side_effect=CategorySlugConflictError("dup-slug"))

    client = _client(service)
    csrf_token, _ = _get_csrf(client, "/categories/new")
    response = client.post(
        "/categories",
        data={
            "csrf_token": csrf_token,
            "name": "X",
            "slug": "dup-slug",
            "sort_order": 0,
        },
    )
    assert response.status_code == 409
    assert "уже существует" in response.text


def test_edit_form_renders_for_existing_category(fake_admin_middleware_session) -> None:
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=_make_category(id=7, name="Existing"))

    client = _client(service)
    response = client.get("/categories/7")
    assert response.status_code == 200
    assert "Existing" in response.text


def test_delete_category_with_events_redirects_with_error_param(
    fake_admin_middleware_session,
) -> None:
    service = MagicMock()
    service.delete_category = AsyncMock(side_effect=CategoryHasEventsError(7))

    client = _client(service)
    csrf_token, _ = _get_csrf(client, "/categories/new")
    response = client.post(
        "/categories/7/delete",
        data={"csrf_token": csrf_token},
    )
    assert response.status_code == 302
    assert "error=has_events" in response.headers["location"]
    assert "category_id=7" in response.headers["location"]


def test_delete_category_empty_redirects_clean(fake_admin_middleware_session) -> None:
    service = MagicMock()
    service.delete_category = AsyncMock(return_value=None)

    client = _client(service)
    csrf_token, _ = _get_csrf(client, "/categories/new")
    response = client.post(
        "/categories/7/delete",
        data={"csrf_token": csrf_token},
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/categories"
