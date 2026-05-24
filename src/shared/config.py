"""Типизированный доступ к конфигу через pydantic-settings.

Источник истины — `.env` рядом с корнем репозитория (см. `infra/.env.example`).
Любой модуль импортирует `from src.shared.config import settings` или вызывает
`get_settings()` явно (полезно в тестах: `get_settings.cache_clear()` + новые env).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    Field,
    HttpUrl,
    PositiveFloat,
    PositiveInt,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

__all__ = [
    "AdminSettings",
    "Environment",
    "ExternalRegistrySettings",
    "Settings",
    "get_settings",
    "settings",
]


Environment = Literal["dev", "staging", "prod"]


def _empty_to_none(value: Any) -> Any:
    """Превращает пустую строку из `.env` в `None` (для опциональных полей)."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class AdminSettings(BaseSettings):
    """Параметры веб-админки: секрет cookie-сессии, длительность сессии."""

    model_config = SettingsConfigDict(
        env_prefix="ADMIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    secret_key: SecretStr
    session_hours: PositiveInt = 8
    # Отдельный секрет для CSRF — best practice (не переиспользуем session secret).
    csrf_secret: SecretStr


class ExternalRegistrySettings(BaseSettings):
    """Параметры внешнего реестра пользователей (http-API либо mock).

    Имена env-переменных привязаны через `validation_alias`, чтобы совпадать с
    `infra/.env.example` — там сложилась плоская схема (`EXTERNAL_API_*`,
    `MOCK_REGISTRY_*`), которую префикс bы не покрыл единообразно.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    backend: Literal["mock", "http"] = Field(
        default="mock", validation_alias="EXTERNAL_REGISTRY_BACKEND"
    )
    api_base_url: HttpUrl | None = Field(default=None, validation_alias="EXTERNAL_API_BASE_URL")
    api_token: SecretStr | None = Field(default=None, validation_alias="EXTERNAL_API_TOKEN")
    timeout_connect: PositiveFloat = Field(
        default=2.0, validation_alias="EXTERNAL_API_TIMEOUT_CONNECT"
    )
    timeout_read: PositiveFloat = Field(default=5.0, validation_alias="EXTERNAL_API_TIMEOUT_READ")
    mock_registry_file: Path | None = Field(default=None, validation_alias="MOCK_REGISTRY_FILE")
    # NoDecode говорит pydantic-settings: не пытаться JSON-парсить значение;
    # CSV-разбор делаем сами в _parse_csv ниже.
    mock_registry_allowed: Annotated[list[str], NoDecode] = Field(
        default_factory=list, validation_alias="MOCK_REGISTRY_ALLOWED"
    )

    @field_validator("api_base_url", "api_token", "mock_registry_file", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @field_validator("mock_registry_allowed", mode="before")
    @classmethod
    def _parse_csv(cls, value: Any) -> Any:
        # Принимаем как CSV-строку из .env, так и уже-список (при программном вызове).
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _check_http_backend_has_credentials(self) -> Self:
        if self.backend == "http" and (self.api_base_url is None or self.api_token is None):
            raise ValueError(
                "EXTERNAL_REGISTRY_BACKEND=http требует EXTERNAL_API_BASE_URL и EXTERNAL_API_TOKEN"
            )
        return self


class Settings(BaseSettings):
    """Корневой конфиг приложения.

    Чтение `.env` делегируется pydantic-settings. Вложенные модели (`admin`,
    `external_registry`) — самостоятельные `BaseSettings`, они тоже читают тот же
    `.env`, поэтому плоская схема переменных (`ADMIN_*`, `EXTERNAL_*`) работает
    без специальных делимитеров.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: SecretStr
    database_url: PostgresDsn
    redis_url: RedisDsn
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    reminder_tick_seconds: PositiveInt = 300
    # `dev` — локальная разработка через http (Secure-cookie отключается).
    # `staging`/`prod` — за https, Secure обязателен.
    environment: Environment = "dev"

    admin: AdminSettings = Field(default_factory=AdminSettings)  # type: ignore[arg-type]
    external_registry: ExternalRegistrySettings = Field(default_factory=ExternalRegistrySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Кэшированный конструктор `Settings()`. Сбрасывается через `get_settings.cache_clear()`."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()


def _redacted_dump(s: Settings) -> str:
    """Однострочное представление настроек со скрытыми SecretStr — для демо-точки.

    `repr` BaseModel в Pydantic v2 уже маскирует `SecretStr` как `**********`,
    в отличие от `model_dump_json`, который сериализует сырые значения.
    """
    return repr(s)


if __name__ == "__main__":  # pragma: no cover
    print(_redacted_dump(get_settings()))
