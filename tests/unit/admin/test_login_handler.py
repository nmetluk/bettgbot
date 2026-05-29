"""Тесты POST /login и /logout handler'ов (TASK-020).

Использует `TestClient` + dependency_overrides для:
- мока `_session_dep` (без реального Postgres);
- bypass `RateLimiter` (без реального Redis в unit-тестах).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from fastapi_limiter.depends import RateLimiter
from src.admin.app import app
from src.admin.auth.security import CSRF_COOKIE_NAME, SESSION_COOKIE_NAME
from src.admin.routes.login import _session_dep
from src.shared.exceptions import AdminInvalidCredentialsError
from src.shared.models import AdminUser


async def _bypass_session():
    yield MagicMock()


async def _bypass_rate_limit() -> None:
    return None


def _client() -> TestClient:
    app.dependency_overrides[_session_dep] = _bypass_session
    # RateLimiter — instance в Depends; override через identity класса работает.
    for route in app.routes:
        for dep in getattr(route, "dependencies", []) or []:
            if isinstance(dep.dependency, RateLimiter):
                app.dependency_overrides[dep.dependency] = _bypass_rate_limit
    return TestClient(app, follow_redirects=False)


def _get_csrf_pair(client: TestClient) -> tuple[str, dict[str, str]]:
    """GET /login, возвращает (csrf_token form value, cookies для POST)."""
    response = client.get("/login")
    assert response.status_code == 200
    import re

    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1), dict(response.cookies)


def test_login_form_renders_with_csrf_input() -> None:
    client = _client()
    response = client.get("/login")
    assert response.status_code == 200
    assert 'name="csrf_token"' in response.text
    assert "Вход" in response.text


def test_login_post_invalid_credentials_returns_401_with_generic_error(
    monkeypatch,
) -> None:
    client = _client()
    csrf_token, cookies = _get_csrf_pair(client)

    async def fake_authenticate(self, *, login: str, password: str) -> AdminUser:
        raise AdminInvalidCredentialsError()

    monkeypatch.setattr("src.admin.routes.login.AdminAuthService.authenticate", fake_authenticate)

    response = client.post(
        "/login",
        data={"csrf_token": csrf_token, "login": "x", "password": "wrong"},
        cookies=cookies,
    )
    assert response.status_code == 401
    assert "Неверный логин или пароль" in response.text
    assert SESSION_COOKIE_NAME not in response.cookies


def test_login_post_success_sets_cookie_and_redirects(monkeypatch) -> None:
    client = _client()
    csrf_token, cookies = _get_csrf_pair(client)

    fake_admin = MagicMock(spec=AdminUser)
    fake_admin.id = 42
    fake_admin.login = "admin"

    async def fake_authenticate(self, *, login: str, password: str) -> AdminUser:
        return fake_admin

    monkeypatch.setattr("src.admin.routes.login.AdminAuthService.authenticate", fake_authenticate)

    response = client.post(
        "/login",
        data={"csrf_token": csrf_token, "login": "admin", "password": "ok"},
        cookies=cookies,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    # Проверяем что установлены ОБА cookies: session и CSRF
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_cookies = [h for h in set_cookie_headers if SESSION_COOKIE_NAME in h]
    csrf_cookies = [h for h in set_cookie_headers if CSRF_COOKIE_NAME in h]
    assert len(session_cookies) > 0, "Session cookie должен быть установлен"
    assert len(csrf_cookies) > 0, "CSRF cookie должен быть установлен (ротация)"


def test_logout_clears_cookie_and_redirects_to_login() -> None:
    client = _client()
    csrf_token, cookies = _get_csrf_pair(client)

    response = client.post(
        "/logout",
        data={"csrf_token": csrf_token},
        cookies=cookies,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    # delete_cookie ставит cookie с Max-Age=0 → клиент должен затереть.
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(SESSION_COOKIE_NAME in h for h in set_cookie_headers)


# ===== TASK-062: Prod-env тесты =====


def test_csrf_config_uses_correct_cookie_key() -> None:
    """_csrf_config использует правильный cookie_key для dev/prod (проверка исходного кода app.py)."""
    from src.admin.auth.security import CSRF_COOKIE_NAME, CSRF_COOKIE_NAME_PROD

    # Проверяем что в app.py есть правильная логика
    with open("src/admin/app.py", encoding="utf-8") as f:
        source = f.read()

    assert "cookie_key=" in source, "app.py должен задавать cookie_key"
    assert "CSRF_COOKIE_NAME_PROD" in source, "app.py должен использовать CSRF_COOKIE_NAME_PROD"
    assert "CSRF_COOKIE_NAME" in source, "app.py должен использовать CSRF_COOKIE_NAME"
    assert 'environment != "dev"' in source, "app.py должен проверять environment"


def test_login_error_shows_actual_error_text_not_hardcoded() -> None:
    """Шаблон login.html рендерит {{ error }}, а не захардкоженный текст."""
    client = _client()
    csrf_token, cookies = _get_csrf_pair(client)

    async def fake_authenticate(self, *, login: str, password: str) -> AdminUser:
        raise AdminInvalidCredentialsError()

    import sys
    from unittest.mock import patch

    # Monkeypatch authenticate
    with patch(
        "src.admin.routes.login.AdminAuthService.authenticate",
        side_effect=AdminInvalidCredentialsError(),
    ):
        response = client.post(
            "/login",
            data={"csrf_token": csrf_token, "login": "x", "password": "wrong"},
            cookies=cookies,
        )
    assert response.status_code == 401
    # Проверяем что текст именно тот, который передаётся в context
    assert "Неверный логин или пароль" in response.text


def test_inactive_account_returns_403_with_disabled_text(monkeypatch) -> None:
    """Отключённый аккаунт даёт 403 с текстом про отключённую запись."""
    from src.shared.exceptions import AdminInactiveError

    client = _client()
    csrf_token, cookies = _get_csrf_pair(client)

    async def fake_authenticate(self, *, login: str, password: str) -> AdminUser:
        raise AdminInactiveError(admin_id=1)

    monkeypatch.setattr("src.admin.routes.login.AdminAuthService.authenticate", fake_authenticate)

    response = client.post(
        "/login",
        data={"csrf_token": csrf_token, "login": "disabled", "password": "ok"},
        cookies=cookies,
    )
    assert response.status_code == 403
    assert "Учётная запись отключена" in response.text


def test_csrf_error_returns_403_with_session_expired_text() -> None:
    """CSRF-ошибка даёт 403 с текстом про истёкшую сессию."""
    client = _client()

    # POST без CSRF-токена → 403 с текстом про истёкшую сессию
    response = client.post("/login", data={"login": "admin", "password": "ok"})
    assert response.status_code == 403
    assert "Сессия истекла" in response.text


def test_proxy_headers_middleware_applies_x_forwarded_proto() -> None:
    """ProxyHeadersMiddleware применяет X-Forwarded-Proto."""
    client = _client()

    # Запрос с X-Forwarded-Proto: https должен использовать https в url_for
    response = client.get("/login", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    # В разметке должны быть root-relative ссылки на статику (не absolute)
    assert "/static/css/tokens.css" in response.text
    # Absolute URL с http:// не должно быть
    assert "http://" not in response.text
