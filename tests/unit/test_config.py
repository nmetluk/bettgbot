"""Тесты для `src.shared.config`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.shared.config import ExternalRegistrySettings, Settings, get_settings


def _set_minimum_env(mp: pytest.MonkeyPatch) -> None:
    mp.setenv("TELEGRAM_BOT_TOKEN", "tg-token-xyz")
    mp.setenv("DATABASE_URL", "postgresql+asyncpg://alice:secret@db.example:5432/app")
    mp.setenv("REDIS_URL", "redis://cache.example:6379/3")
    mp.setenv("ADMIN_SECRET_KEY", "cookie-secret")


def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")
    monkeypatch.setenv("REMINDER_TICK_SECONDS", "120")
    monkeypatch.setenv("ADMIN_SESSION_HOURS", "4")
    monkeypatch.setenv("EXTERNAL_REGISTRY_BACKEND", "mock")
    monkeypatch.setenv("MOCK_REGISTRY_FILE", "infra/mock-registry.yml")
    monkeypatch.setenv("MOCK_REGISTRY_ALLOWED", "")

    s = Settings()  # type: ignore[call-arg]

    assert s.telegram_bot_token.get_secret_value() == "tg-token-xyz"
    assert str(s.database_url).startswith("postgresql+asyncpg://alice:")
    assert "cache.example" in str(s.redis_url)
    assert s.log_level == "DEBUG"
    assert s.log_format == "console"
    assert s.reminder_tick_seconds == 120
    assert s.admin.secret_key.get_secret_value() == "cookie-secret"
    assert s.admin.session_hours == 4
    assert s.external_registry.backend == "mock"
    assert s.external_registry.mock_registry_allowed == []


def test_config_secret_fields_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "super-secret-token")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "very-secret")

    s = Settings()  # type: ignore[call-arg]

    assert "super-secret-token" not in repr(s)
    assert "super-secret-token" not in str(s.telegram_bot_token)
    assert "very-secret" not in repr(s)
    assert s.telegram_bot_token.get_secret_value() == "super-secret-token"


def test_config_http_backend_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("EXTERNAL_REGISTRY_BACKEND", "http")
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "")
    monkeypatch.setenv("EXTERNAL_API_TOKEN", "")

    with pytest.raises(ValidationError, match="EXTERNAL_REGISTRY_BACKEND=http"):
        Settings()  # type: ignore[call-arg]


def test_config_mock_allowed_parses_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("EXTERNAL_REGISTRY_BACKEND", "mock")
    monkeypatch.setenv("MOCK_REGISTRY_ALLOWED", " +711 , +722, ")

    s = ExternalRegistrySettings()  # type: ignore[call-arg]

    assert s.mock_registry_allowed == ["+711", "+722"]


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second

    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    get_settings.cache_clear()
    third = get_settings()
    assert third.log_level == "ERROR"
    assert third is not first
