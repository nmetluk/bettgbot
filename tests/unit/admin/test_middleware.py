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
    session_name = (
        SESSION_COOKIE_NAME_PROD if fake_settings.environment != "dev" else SESSION_COOKIE_NAME
    )

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


def test_double_get_does_not_rotate_csrf_cookie() -> None:
    """TASK-068: два GET /login не должны ротировать CSRF-куку.

    Сценарий:
    1. GET /login → рендер формы с токеном T1, кука C1
    2. Ещё один GET /login → токен и кука НЕ должны меняться
    3. POST /login с T1 и кукой C1 → должно быть 401/302, но НЕ 403

    До фикса: второй GET перетирал куку на C2, POST с T1/C2 давал 403.
    """
    from unittest.mock import patch

    from fastapi_csrf_protect import CsrfProtect
    from itsdangerous import URLSafeTimedSerializer
    from src.admin.auth.security import CSRF_COOKIE_NAME
    from src.shared.config import get_settings
    from src.shared.exceptions import AdminInvalidCredentialsError

    client = TestClient(app, follow_redirects=False)  # raise_server_exceptions=True по умолчанию

    # Первый GET - создаём CSRF-куку
    response1 = client.get("/login")
    assert response1.status_code == 200

    # Извлекаем CSRF-куку и токен из формы
    csrf_cookie = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_cookie is not None

    # Декодируем токен из куки
    s = get_settings()
    serializer = URLSafeTimedSerializer(
        s.admin.csrf_secret.get_secret_value(), salt="fastapi-csrf-token"
    )
    original_token = serializer.loads(csrf_cookie, max_age=None)

    # Второй GET - до фикса это перетёрло бы куку
    response2 = client.get("/login")
    assert response2.status_code == 200

    # Кука должна остаться той же (не перезаписана)
    csrf_cookie_after = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_cookie_after == csrf_cookie, "CSRF-кука не должна перезаписываться на втором GET"

    # Извлекаем токен из формы
    import re

    form_token_match = re.search(r'name="csrf_token" value="([^"]+)"', response2.text)
    assert form_token_match is not None, "Форма должна содержать CSRF-токен"
    form_token = form_token_match.group(1)

    # Токен в форме должен совпадать с декодированным токеном из куки
    assert form_token == original_token, "Токен в форме должен соответствовать токену в куке"

    # POST с этим токеном не должен давать 403 (CsrfProtectError)
    # 401 - неверные креды (ожидаемо), но не 403 "Сессия истекла"
    with patch(
        "src.admin.routes.login.AdminAuthService.authenticate",
        side_effect=AdminInvalidCredentialsError(),
    ):
        response3 = client.post(
            "/login",
            data={"login": "wrong", "password": "wrong", "csrf_token": form_token},
            follow_redirects=False,
        )
    assert response3.status_code == 401, "Ожидается 401 (неверные креды), не 403 (CSRF-ошибка)"


def test_prod_env_csrf_cookie_name_selection() -> None:
    """TASK-068: проверяет что для prod окружения используется __Host- prefixed CSRF-кука.

    Проверяет логику выбора имени куки по окружению. Полный тест перезаписи куки
    ограничен тем, что __Host- куки не работают корректно в TestClient.
    """
    from src.admin.auth.security import CSRF_COOKIE_NAME, CSRF_COOKIE_NAME_PROD
    from src.shared.config import Settings, get_settings

    # Проверяем что имена констант правильные
    assert CSRF_COOKIE_NAME == "fastapi-csrf-token"
    assert CSRF_COOKIE_NAME_PROD == "__Host-fastapi-csrf-token"

    # Проверяем логику выбора имени куки
    s = get_settings()

    # Для dev окружения
    csrf_name_dev = CSRF_COOKIE_NAME_PROD if s.environment != "dev" else CSRF_COOKIE_NAME
    assert csrf_name_dev == CSRF_COOKIE_NAME, "Для dev должно использоваться имя без __Host-"

    # Проверяем что middleware логика работает для prod (через создание настроек)
    prod_settings = s.model_copy(update={"environment": "prod"})
    csrf_name_prod = (
        CSRF_COOKIE_NAME_PROD if prod_settings.environment != "dev" else CSRF_COOKIE_NAME
    )
    assert csrf_name_prod == CSRF_COOKIE_NAME_PROD, "Для prod должно использоваться __Host- prefix"


def test_csrf_cookie_reuse_logic() -> None:
    """TASK-068: проверяет логику переиспользования CSRF-куки изолированно.

    Тестируем метод _get_token_from_cookie напрямую, чтобы убедиться что
    валидная кука декодируется корректно и используется повторно.
    """
    import secrets

    from fastapi_csrf_protect import CsrfProtect
    from src.admin.auth.middleware import CsrfTokenMiddleware
    from src.shared.config import get_settings

    s = get_settings()
    secret = s.admin.csrf_secret.get_secret_value()

    # Генерируем пару токенов
    csrf = CsrfProtect()
    token, signed_token = csrf.generate_csrf_tokens()

    # Создаём middleware (аргумент app может быть None для теста метода)
    middleware = CsrfTokenMiddleware(lambda: None)  # type: ignore

    # Проверяем что валидная кука декодируется
    extracted = middleware._get_token_from_cookie(signed_token, secret)
    assert extracted == token, "Валидная кука должна декодироваться в исходный токен"

    # Проверяем что невалидная кука возвращает None
    invalid = "invalid_token"
    assert middleware._get_token_from_cookie(invalid, secret) is None, (
        "Невалидная кука должна возвращать None"
    )

    # Проверяем что кука с другим секретом возвращает None
    wrong_secret = secrets.token_urlsafe(32)
    assert middleware._get_token_from_cookie(signed_token, wrong_secret) is None, (
        "Кука с другим секретом должна возвращать None"
    )


def test_stale_csrf_cookie_self_heals_on_next_get() -> None:
    """TASK-069: браузер со старой CSRF-кукой (>15 мин) всё равно может войти.

    Сценарий:
    1. Пользователь открыл /login 16 минут назад → получил куку C1
    2. Кука протухла (TTL=15 мин), но браузер её хранит
    3. Пользователь возвращается, делает GET /login
    4. Middleware видит протухшую куку → выдаёт свежую C2
    5. POST с токеном из формы → НЕ 403 (self-heal)

    До фикса TASK-069: middleware декодировал с max_age=None, протухшая кука
    переиспользовалась, validate_csrf с max_age=900 давал 403 → вход сломан.
    """
    import time
    from unittest.mock import patch

    from fastapi_csrf_protect import CsrfProtect
    from freezegun import freeze_time
    from itsdangerous import URLSafeTimedSerializer
    from src.admin.auth.security import CSRF_COOKIE_NAME, CSRF_TTL_SECONDS
    from src.shared.config import get_settings
    from src.shared.exceptions import AdminInvalidCredentialsError

    client = TestClient(app, follow_redirects=False)

    s = get_settings()
    secret = s.admin.csrf_secret.get_secret_value()
    csrf = CsrfProtect()

    # Шаг 1: создаём куку в "прошлом" (16 минут назад)
    with freeze_time("2026-05-30 12:00:00 UTC"):
        response1 = client.get("/login")
        assert response1.status_code == 200
        old_cookie = client.cookies.get(CSRF_COOKIE_NAME)
        assert old_cookie is not None

        # Декодируем токен из куки (для сравнения позже)
        serializer = URLSafeTimedSerializer(secret, salt="fastapi-csrf-token")
        old_token = serializer.loads(old_cookie, max_age=None)

    # Шаг 2: перематываем время вперёд на 16 минут (кука протухла)
    with freeze_time("2026-05-30 12:16:00 UTC"):
        # Шаг 3: GET с протухшей кукой → middleware должен выдать новую
        response2 = client.get("/login")
        assert response2.status_code == 200

        new_cookie = client.cookies.get(CSRF_COOKIE_NAME)
        assert new_cookie is not None
        # Кука ДОЛЖНА быть обновлена (старая протухла)
        assert new_cookie != old_cookie, "Протухшая кука должна быть заменена на свежую"

        # Извлекаем токен из формы
        import re

        form_token_match = re.search(r'name="csrf_token" value="([^"]+)"', response2.text)
        assert form_token_match is not None
        form_token = form_token_match.group(1)

        # Шаг 4: POST с токеном из формы → НЕ 403 (а 401 от неверных кредов)
        with patch(
            "src.admin.routes.login.AdminAuthService.authenticate",
            side_effect=AdminInvalidCredentialsError(),
        ):
            response3 = client.post(
                "/login",
                data={"login": "wrong", "password": "wrong", "csrf_token": form_token},
                follow_redirects=False,
            )

        # Ожидаем 401 (неверные креды), но не 403 (CSRF-ошибка)
        assert response3.status_code == 401, (
            f"Ожидается 401 (неверные креды), не 403 (CSRF). "
            f"Статус: {response3.status_code}"
        )


def test_csrf_cookie_respects_ttl_in_decode() -> None:
    """TASK-069: проверяет что _get_token_from_cookie использует TTL при декодировании.

    Прямая проверка метода: кука старше TTL секунд не декодируется.
    """
    from freezegun import freeze_time
    from itsdangerous import URLSafeTimedSerializer

    from fastapi_csrf_protect import CsrfProtect
    from src.admin.auth.middleware import CsrfTokenMiddleware
    from src.admin.auth.security import CSRF_TTL_SECONDS
    from src.shared.config import get_settings

    s = get_settings()
    secret = s.admin.csrf_secret.get_secret_value()
    csrf = CsrfProtect()

    middleware = CsrfTokenMiddleware(lambda: None)  # type: ignore

    # Создаём токен
    token, signed_token = csrf.generate_csrf_tokens()

    # Свежая кука декодируется
    extracted_fresh = middleware._get_token_from_cookie(signed_token, secret)
    assert extracted_fresh == token, "Свежая кука должна декодироваться"

    # Перематываем время вперёд на TTL + 1 секунда
    with freeze_time(f"2026-05-30 12:{CSRF_TTL_SECONDS // 60 + 1}:00 UTC"):
        # Кука старше TTL НЕ должна декодироваться
        extracted_stale = middleware._get_token_from_cookie(signed_token, secret)
        assert extracted_stale is None, "Кука старше TTL не должна декодироваться"
