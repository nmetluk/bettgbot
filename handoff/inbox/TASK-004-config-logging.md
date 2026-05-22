---
id: TASK-004
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/02-tech-stack.md
  - docs/08-conventions.md
  - infra/.env.example
priority: high
estimate: M
---

# TASK-004: Конфиг-слой и структурное логирование

## Контекст

После TASK-003 у нас есть `.env.example` со всеми переменными, поднимающаяся compose-инфра и пустой `src/shared/`. Перед тем как писать модели (TASK-005), нужен типизированный доступ к конфигу и единая настройка логирования. Иначе каждый следующий модуль начнёт `os.getenv` и собственные `logging.basicConfig` — потом не вычистим.

[docs/02-tech-stack.md](../../docs/02-tech-stack.md) фиксирует выбор `pydantic-settings` для конфига и `structlog` для логов. [docs/08-conventions.md](../../docs/08-conventions.md) требует `logger = structlog.get_logger(__name__)` и единый стиль `logger.info("event", key=value)` вместо f-строк.

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: дополнен `infra/.env.example` (dev/compose-варианты URL), переписан `docs/07-deployment.md` (раскладка compose), новые записи в `state/PROJECT_STATUS.md` и `state/DECISIONS.md`, новая сессия `sessions/2026-05-23-02-task-003-review/`. Упакуй в `chore/post-TASK-003-cowork-cleanup`, открой PR, мёрджи. После — ветка `feature/TASK-004-config-logging` от свежего `main`.

## Цель

В `src/shared/` есть `config.py` с типизированным `Settings`-объектом и `logging.py` с инициализацией structlog. Любой модуль может сделать `from src.shared.config import settings` и `from src.shared.logging import get_logger` и сразу работать. Покрыты тестами.

## Definition of Done

- [ ] **`src/shared/config.py`:**
  - класс `Settings(BaseSettings)` из `pydantic-settings>=2.2`
  - `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid", case_sensitive=False)`
  - все переменные из [`infra/.env.example`](../../infra/.env.example), сгруппированы вложенными моделями, где это естественно:
    - корневые: `telegram_bot_token: SecretStr`, `database_url: PostgresDsn`, `redis_url: RedisDsn`, `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]`, `log_format: Literal["json","console"]`, `reminder_tick_seconds: PositiveInt`
    - вложенная `admin: AdminSettings` (`secret_key: SecretStr`, `session_hours: PositiveInt = 8`) — через префикс `ADMIN_`
    - вложенная `external_registry: ExternalRegistrySettings` (`backend: Literal["mock","http"]`, `api_base_url: HttpUrl | None`, `api_token: SecretStr | None`, `timeout_connect: PositiveFloat`, `timeout_read: PositiveFloat`, `mock_registry_file: Path | None`, `mock_registry_allowed: list[str]` — парсинг из CSV) — через префикс `EXTERNAL_`
  - **валидаторы:**
    - если `external_registry.backend == "http"` — `api_base_url` и `api_token` обязательны, иначе `ValueError` на этапе загрузки
    - если `external_registry.backend == "mock"` и заданы оба `mock_registry_file` и `mock_registry_allowed` — это норм (allowed имеет приоритет, см. [docs/06-external-api.md](../../docs/06-external-api.md))
  - **singleton-доступ:** `@lru_cache def get_settings() -> Settings`, и `settings: Settings = get_settings()` на уровне модуля для удобства импорта. Тесты — через `get_settings.cache_clear()`
  - docstring уровня модуля + публичный API ограничен `__all__ = ["Settings", "AdminSettings", "ExternalRegistrySettings", "get_settings", "settings"]`
- [ ] **`src/shared/logging.py`:**
  - функция `configure_logging(level: str, format: Literal["json","console"]) -> None`:
    - `structlog.configure(...)` с processor-chain
    - `format = "json"` → `structlog.processors.JSONRenderer()`
    - `format = "console"` → `structlog.dev.ConsoleRenderer(colors=True)`
    - timestamp в ISO-формате (`structlog.processors.TimeStamper(fmt="iso")`)
    - корреляционные поля через `structlog.contextvars.merge_contextvars`
    - stdlib `logging` тоже перенаправляется в structlog (`structlog.stdlib.ProcessorFormatter` + `structlog.stdlib.add_log_level`), чтобы логи из aiogram/sqlalchemy/uvicorn попадали в общую трубу
  - функция `get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger` — тонкая обёртка над `structlog.get_logger`
  - **idempotency:** повторный вызов `configure_logging` не плодит handler'ов
  - docstring уровня модуля, `__all__`
- [ ] **Демо-точка:** `python -m src.shared.config` — печатает текущий `Settings()` в одну строку (с замаской secret-полей: `SecretStr` показывается как `**********`). Это удобно, чтобы убедиться, что `.env` подхватился.
- [ ] **Тесты (`tests/unit/`):**
  - `test_config_loads_from_env_file`: создать tmp-`.env`, прочитать через `Settings(_env_file=tmpfile)`, проверить значения
  - `test_config_secret_fields_are_redacted`: `repr(settings)` и `str(settings.telegram_bot_token)` не содержат сырого значения
  - `test_config_http_backend_requires_token`: backend=http без token → `ValidationError`
  - `test_config_mock_allowed_parses_csv`: `EXTERNAL_MOCK_REGISTRY_ALLOWED="+711,+722"` → `[" +711", "+722"]` после нормализации
  - `test_logging_json_format`: capture stdout, `configure_logging("INFO","json")`, `get_logger().info("event", x=1)` → строка валидный JSON с полями `event`, `x`, `level`, `timestamp`
  - `test_logging_console_format`: capture stdout, тот же сценарий с `console` — проверить наличие текста, без строгого формата
  - `test_logging_idempotent`: дважды вызвать `configure_logging`, один лог даёт одну строку (не дублируется)
- [ ] **Mypy strict зелёный** на `src/shared/`. `pydantic-settings` имеет stubs из коробки, отдельных overrides не нужно. Если `structlog` ругается — добавить точечный override в `pyproject.toml`.
- [ ] **Ruff** зелёный (включая format).
- [ ] **pytest** зелёный (все новые тесты, smoke-тест из TASK-002 не сломан).
- [ ] **CI** зелёный на PR.
- [ ] Ветка `feature/TASK-004-config-logging`, Conventional Commits, PR.
- [ ] Отчёт `handoff/outbox/TASK-004-report.md`.
- [ ] Задача → `handoff/archive/TASK-004-config-logging/task.md`.

## Артефакты

```
+ src/shared/config.py
+ src/shared/logging.py
* src/shared/__init__.py                    # обновить __all__
+ tests/unit/test_config.py
+ tests/unit/test_logging.py
* tests/unit/test_smoke.py                  # не трогать, должен оставаться зелёным
```

## Ссылки

- [docs/02-tech-stack.md](../../docs/02-tech-stack.md) — выбор pydantic-settings и structlog
- [docs/08-conventions.md](../../docs/08-conventions.md) — стиль `logger.info("event", k=v)`
- [docs/06-external-api.md](../../docs/06-external-api.md) — почему mock_registry_allowed имеет приоритет над mock_registry_file
- [infra/.env.example](../../infra/.env.example) — источник переменных

## Подсказки исполнителю

- **Вложенные модели** — через `model_config = SettingsConfigDict(env_nested_delimiter="__")` или через `class AdminSettings: model_config = SettingsConfigDict(env_prefix="ADMIN_")` (вариант с префиксами лучше читается в `.env` — оставляем переменные плоскими: `ADMIN_SECRET_KEY`, `EXTERNAL_API_TOKEN` и т.д.). Поле в `Settings` — `admin: AdminSettings = AdminSettings()` (default_factory pattern).
- **CSV-список** в `mock_registry_allowed`: добавить `@field_validator("mock_registry_allowed", mode="before")` или `BeforeValidator`, делать `split(",")` + `strip()`.
- **SecretStr в `pydantic-settings` v2** скрывает значение в `repr`. Для проверки тестом — `secret.get_secret_value()`.
- **structlog + stdlib bridging**: канонический рецепт — `structlog.stdlib.ProcessorFormatter` + `logging.basicConfig(handlers=[handler])`. Готовая формула:
  ```python
  import logging
  import structlog

  shared_processors = [
      structlog.contextvars.merge_contextvars,
      structlog.stdlib.add_log_level,
      structlog.processors.TimeStamper(fmt="iso", utc=True),
  ]

  def configure_logging(level: str, format: str) -> None:
      renderer = (
          structlog.processors.JSONRenderer()
          if format == "json"
          else structlog.dev.ConsoleRenderer(colors=True)
      )
      structlog.configure(
          processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
          wrapper_class=structlog.stdlib.BoundLogger,
          logger_factory=structlog.stdlib.LoggerFactory(),
          cache_logger_on_first_use=True,
      )
      handler = logging.StreamHandler()
      handler.setFormatter(structlog.stdlib.ProcessorFormatter(
          foreign_pre_chain=shared_processors,
          processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
      ))
      root = logging.getLogger()
      root.handlers.clear()  # idempotency
      root.addHandler(handler)
      root.setLevel(level)
  ```
- **Капчинг логов в тесте**: `capsys` фикстура pytest + перенаправление root logger handler'а в `sys.stdout`.
- **Capturing in CI**: `LOG_FORMAT=json` в CI (как и в prod). Не надо в pytest менять глобальный formatter — конфигурируй внутри теста через `configure_logging`, и в финальном `conftest.py` (опционально) сбрасывай handlers после каждого теста через autouse-фикстуру.
- **PostgresDsn / RedisDsn**: в pydantic v2 они доступны как `pydantic.PostgresDsn`, `pydantic.RedisDsn`. Driver `postgresql+asyncpg://` валиден.
- **HttpUrl + None**: используй `HttpUrl | None = None`, валидатор `model_validator(mode="after")` для проверки «http backend → token и url не None».

## Что НЕ делать

- Не подключать `python-dotenv` отдельно — `pydantic-settings` сама умеет читать `.env`.
- Не писать никаких моделей БД, SQLAlchemy, миграций — это TASK-005 и TASK-006.
- Не подключать sentry/OTel/другие наблюдательные системы — это будущая отдельная задача.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не добавлять зависимости, которых нет в `pyproject.toml` (там уже есть `structlog`, `pydantic`, `pydantic-settings`).
