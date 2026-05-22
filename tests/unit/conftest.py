"""Глобальный conftest: подкладывает минимальные env-переменные ДО импорта тестов.

`src.shared.config` на верхнем уровне выполняет `settings = get_settings()`, что
читает `.env`. В CI и при изолированном прогоне `.env` нет — без этих stub'ов
импорт упал бы с `ValidationError`. Сами тесты конфига создают `Settings`
явно (`Settings(_env_file=tmpfile)` или с переопределёнными env), поэтому
stub-значения тут не влияют на их корректность.
"""

from __future__ import annotations

import os

_STUB_ENV: dict[str, str] = {
    "TELEGRAM_BOT_TOKEN": "stub-bot-token",
    "DATABASE_URL": "postgresql+asyncpg://stub:stub@localhost:5432/stub",
    "REDIS_URL": "redis://localhost:6379/0",
    "ADMIN_SECRET_KEY": "stub-admin-secret-key",
    "EXTERNAL_REGISTRY_BACKEND": "mock",
    "LOG_LEVEL": "INFO",
    "LOG_FORMAT": "json",
}

for _key, _value in _STUB_ENV.items():
    os.environ.setdefault(_key, _value)
