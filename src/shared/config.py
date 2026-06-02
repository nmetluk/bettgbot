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
    "BackupSettings",
    "Environment",
    "ObservabilitySettings",
    "Settings",
    "get_settings",
    "settings",
]


Environment = Literal["dev", "staging", "prod"]

_WEAK_SECRET_MARKERS = frozenset({"dev-", "changeme", "secret", "test"})


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
    # SameSite для session + CSRF cookies. Strict для admin-only UI (без внешних ссылок).
    session_samesite: Literal["lax", "strict"] = "strict"


class BackupSettings(BaseSettings):
    """Параметры offsite backup: age шифрование + rclone.

    В dev по умолчанию выключено; в prod требует явного BACKUP_ENABLED=true
    и настройки age_recipient + rclone_remote.
    """

    model_config = SettingsConfigDict(
        env_prefix="BACKUP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = False
    # Публичный ключ age для шифрования (private хранится у владельца вне VPS).
    age_recipient: str | None = None
    # rclone remote (например `b2:bettgbot-backups` или `s3:bucket/path`).
    rclone_remote: str | None = None
    # Сколько дней хранить бэкапы в offside (local volume через find -mtime).
    retention_days: PositiveInt = 30

    # TASK-099: heartbeat-мониторинг бэкапов внутри бота (через backup_run таблицу).
    # Включает ежечасный джоб send_backup_health_heartbeat (только если true).
    # Заменяет primary-guard — включаем флаг на одном инстансе бота.
    heartbeat_enabled: bool = False
    # Порог просрочки последнего успешного бэкапа (алерт если старше).
    max_age_hours: PositiveInt = 2

    # TASK-100: репликация дампа с Admin-сервера на Bot-сервер (pull по SSH/rsync).
    # Включает джоб replicate_latest_backup. Ключи между серверами — деплой-предпосылка.
    replication_enabled: bool = False
    # Хост Admin-сервера (источник дампов). Если None — можно fallback на ADMIN_DOMAIN в джобе.
    source_host: str | None = None
    source_ssh_user: str = "root"
    ssh_key_path: Path = Path("/etc/ssh/keys/id_rsa")
    source_dir: str = "/backups"
    local_dir: Path = Path("/backups")
    # Порог, после которого "не реплицирован" считается просрочкой (для алерта в heartbeat).
    replication_max_lag_hours: PositiveInt = 3

    @field_validator("age_recipient", "rclone_remote", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        return _empty_to_none(value)

    @model_validator(mode="after")
    def _check_enabled_has_required_fields(self) -> Self:
        if self.enabled:
            if not self.age_recipient:
                raise ValueError("BACKUP_ENABLED=true требует BACKUP_AGE_RECIPIENT")
            if not self.rclone_remote:
                raise ValueError("BACKUP_ENABLED=true требует BACKUP_RCLONE_REMOTE")
        return self

    @model_validator(mode="after")
    def _check_replication_has_required_fields(self) -> Self:
        if self.replication_enabled:
            if not self.source_ssh_user:
                raise ValueError("BACKUP_REPLICATION_ENABLED=true требует BACKUP_SOURCE_SSH_USER")
            if not self.ssh_key_path:
                raise ValueError("BACKUP_REPLICATION_ENABLED=true требует BACKUP_SSH_KEY_PATH")
            if not self.source_dir:
                raise ValueError("BACKUP_REPLICATION_ENABLED=true требует BACKUP_SOURCE_DIR")
            if not self.local_dir:
                raise ValueError("BACKUP_REPLICATION_ENABLED=true требует BACKUP_LOCAL_DIR")
        return self


class ObservabilitySettings(BaseSettings):
    """Параметры observability: Sentry для ошибок, Healthchecks.io для uptime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Sentry DSN (Data Source Name) — если None, Sentry отключён.
    sentry_dsn: SecretStr | None = None
    # Процент транзакций для tracing perf (0.1 = 10%).
    sentry_traces_sample_rate: float = 0.1
    # Healthchecks.io ping URL — если None, пинг отключён.
    healthchecks_ping_url: HttpUrl | None = None

    @field_validator("healthchecks_ping_url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        return _empty_to_none(value)


class Settings(BaseSettings):
    """Корневой конфиг приложения.

    Чтение `.env` делегируется pydantic-settings. Вложенные модели (`admin`,
    `backup`, `observability`) — самостоятельные `BaseSettings`, они тоже читают
    тот же `.env`, поэтому плоская схема переменных работает без делимитеров.
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
    log_format: Literal["json", "console"] = "console"
    reminder_tick_seconds: PositiveInt = 300
    # Окно в минутах для поиска кандидатов напоминаний (TASK-049).
    # Должно быть >= tick_interval + safety_margin для catchup при misfire.
    reminder_window_minutes: PositiveInt = 10
    # Сколько дней хранить записи в reminder_dispatch_log (TASK-048).
    reminder_log_retention_days: PositiveInt = 90
    # `dev` — локальная разработка через http (Secure-cookie отключается).
    # `staging`/`prod` — за https, Secure обязателен.
    environment: Environment = "dev"

    # Список chat_id администраторов для получения служебных сообщений от бота
    # (дневной дайджест + пост-итоговые сводки событий). Пусто → фича выключена.
    # Только для сервиса bot (web не использует). CSV в env, парсинг как старый MOCK_REGISTRY_ALLOWED.
    admin_telegram_chat_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list, validation_alias="ADMIN_TELEGRAM_CHAT_IDS"
    )

    admin: AdminSettings = Field(default_factory=AdminSettings)  # type: ignore[arg-type]
    backup: BackupSettings = Field(default_factory=BackupSettings)  # type: ignore[arg-type]
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)  # type: ignore[arg-type]

    @field_validator("admin_telegram_chat_ids", mode="before")
    @classmethod
    def _parse_admin_telegram_chat_ids(cls, value: Any) -> Any:
        """CSV-строка '123,456' или список → list[int]. Пусто/None/пробелы → []."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            return [int(x) for x in value if str(x).strip()]
        return []

    @model_validator(mode="after")
    def _validate_prod_secrets(self) -> Self:
        """В prod-окружении проверяет, что секреты не являются дефолтными/слабыми."""
        if self.environment == "dev":
            return self

        errors: list[str] = []

        # Проверка admin.secret_key
        secret_key_value = self.admin.secret_key.get_secret_value()
        if (
            any(marker in secret_key_value for marker in _WEAK_SECRET_MARKERS)
            or len(secret_key_value) < 32
        ):
            errors.append("admin.secret_key")

        # Проверка admin.csrf_secret
        csrf_value = self.admin.csrf_secret.get_secret_value()
        if any(marker in csrf_value for marker in _WEAK_SECRET_MARKERS) or len(csrf_value) < 32:
            errors.append("admin.csrf_secret")

        # Проверка telegram_bot_token
        bot_token = self.telegram_bot_token.get_secret_value()
        if bot_token == "dev-bot-token" or len(bot_token) < 30:
            errors.append("telegram_bot_token")

        # Проверка log_format
        if self.log_format == "console":
            errors.append("log_format (должен быть json в prod)")

        if errors:
            raise ValueError(
                f"Невалидные настройки для environment={self.environment}: {', '.join(errors)}. "
                "Сгенерируйте сильные секреты через python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )

        # Prod/staging рекомендует включить Sentry (warning, не error).
        if self.environment in ("prod", "staging") and self.observability.sentry_dsn is None:
            import warnings

            warnings.warn(
                "SENTRY_DSN не задан — рекомендации для prod/staging: "
                "https://docs.sentry.io/platforms/python/",
                UserWarning,
                stacklevel=2,
            )

        return self


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
