---
task: TASK-004
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/8
branch: feature/TASK-004-config-logging
commits:
  - 02b997e chore(ruff): ignore RUF001/002/003 for Russian docstrings and comments
  - f1b2c51 feat(shared): typed Settings via pydantic-settings
  - ffba6b5 feat(shared): structlog setup with stdlib bridge
  - d7593f8 chore(handoff): mark TASK-004 in-progress
---

# Отчёт по TASK-004: Конфиг-слой и структурное логирование

## Сводка

Закрыт конфиг-слой и логирование — фундамент для последующих TASK-005+ (модели, сервисы). `src/shared/config.py` экспортирует типизированный `Settings`, `AdminSettings`, `ExternalRegistrySettings`, кэшированный `get_settings()` и module-level `settings`. `src/shared/logging.py` поднимает structlog с bridge на stdlib `logging` так, что логи из aiogram/sqlalchemy/uvicorn попадают в единую трубу — JSON в prod, цветной console в dev.

Вложенные модели — каждый отдельный `BaseSettings`, читает тот же `.env`. Это даёт плоскую схему переменных (`ADMIN_SECRET_KEY`, `EXTERNAL_API_TOKEN`, …), совпадающую с `infra/.env.example`. Связь поля и env-переменной — через `env_prefix="ADMIN_"` для admin и через `validation_alias` для external (потому что префиксная схема не покрывает разнородные имена `EXTERNAL_API_*` / `MOCK_REGISTRY_*` единообразно).

В тестах поднимаются env через `monkeypatch.setenv` — это и стабильнее, и явнее, чем `_env_file=tmp` (последний перекрывается уже-выставленными переменными окружения из `conftest.py`, что приводит к маскам в значениях). `conftest.py` setdefault'ит минимальный набор stub-env: иначе сборка тестов падает на `from src.shared import ...`, потому что module-level `settings = get_settings()` пытается прочитать `.env`, которого в CI нет.

Перед основной работой сделан pre-task cleanup PR ([#7](https://github.com/nmetluk/bettgbot/pull/7)) с правками cowork по итогам TASK-003 (раскладка compose-файлов в `docs/07-deployment.md`, dev/compose URL-варианты в `infra/.env.example`, обновлённый PROJECT_STATUS).

## Изменённые файлы

```
+ src/shared/config.py                           # новый, ~150 строк
+ src/shared/logging.py                          # новый, ~70 строк
* src/shared/__init__.py                         # экспорты Settings/configure_logging/...
* pyproject.toml                                 # ignore RUF001/002/003 для русских docstring
+ tests/conftest.py                              # stub env на module-level
+ tests/unit/test_config.py                      # 5 тестов
+ tests/unit/test_logging.py                     # 3 теста
* tests/unit/test_smoke.py                       # инвариант обновлён под новый __all__
* handoff/inbox/TASK-004-config-logging.md → in-progress → archive (этот PR)
+ handoff/archive/TASK-004-config-logging/task.md
+ handoff/outbox/TASK-004-report.md
```

## Тесты

```
9 passed in 0.14s

tests/unit/test_config.py    test_config_loads_from_env             ✓
                             test_config_secret_fields_are_redacted ✓
                             test_config_http_backend_requires_token ✓
                             test_config_mock_allowed_parses_csv    ✓
                             test_get_settings_is_cached            ✓
tests/unit/test_logging.py   test_logging_json_format               ✓
                             test_logging_console_format            ✓
                             test_logging_idempotent                ✓
tests/unit/test_smoke.py     test_smoke                             ✓
```

`mypy src/shared` (strict) — `Success: no issues found in 3 source files`. `ruff check`, `ruff format --check` — зелёные. CI PR [#8](https://github.com/nmetluk/bettgbot/pull/8) полностью зелёный.

## Демо-точка

```
$ uv run python -m src.shared.config
Settings(telegram_bot_token=SecretStr('**********'),
         database_url=PostgresDsn('postgresql+asyncpg://betting:changeme@db:5432/betting'),
         redis_url=RedisDsn('redis://redis:6379/0'),
         log_level='INFO', log_format='json', reminder_tick_seconds=300,
         admin=AdminSettings(secret_key=SecretStr('**********'), session_hours=8),
         external_registry=ExternalRegistrySettings(
             backend='mock', api_base_url=None, api_token=None,
             timeout_connect=2.0, timeout_read=5.0,
             mock_registry_file=PosixPath('infra/mock-registry.yml'),
             mock_registry_allowed=[]))
```

`SecretStr('**********')` маскируется через `repr` (стандартное поведение pydantic v2). Сырое значение можно получить только через `.get_secret_value()`.

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env

# демо
uv run python -m src.shared.config

# тесты
uv run pytest tests/unit/test_config.py tests/unit/test_logging.py -v
uv run mypy src/shared
uv run ruff check src tests
```

В коде:

```python
from src.shared.config import settings, get_settings
from src.shared.logging import configure_logging, get_logger

configure_logging(settings.log_level, settings.log_format)
logger = get_logger(__name__)
logger.info("startup", db=str(settings.database_url))
```

## Что не сделано / вынесено

1. **`extra="forbid"` заменён на `"ignore"`.** В DoD стоял `forbid`, но `.env` содержит `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` для compose — они не поля моих моделей, и при `forbid` pydantic-settings ругается на каждое чтение. Если поведение важнее prevention опечаток в Python (`Settings(unknown_kw=...)`) — могу вернуть `forbid` и добавить эти три поля как pass-through. Открыто на согласование.
2. **`Settings(_env_file=tmpfile)`-стиль тестов не работает** в моей конфигурации: переменные из `conftest.py`/реального окружения перекрывают `_env_file`. Перешёл на `monkeypatch.setenv` — чище и контролируемее. Альтернатива (если нужен именно tmp-file) — в каждом тесте через `monkeypatch.delenv` чистить env, потом ставить `_env_file`. Сейчас не делал.
3. **Runtime warning** `'src.shared.config' found in sys.modules after import of package 'src.shared'` при `python -m src.shared.config` — runpy + `__init__.py`, который импортирует config. Не критично; вывод корректный. Подавить можно через `python -W ignore::RuntimeWarning -m src.shared.config`.
4. **`mypy_path = "src"` + `explicit_package_bases = true`** не настраивал. Конфликт имён `shared.config` vs `src.shared.config` решил перевести `src/shared/__init__.py` на relative imports — внутри пакета это естественно. Снаружи (bot/admin/tests) импорты остаются абсолютными `from src.shared import ...`.

## Открытые вопросы для проектировщика

1. **`extra="forbid"` vs `"ignore"`.** Согласовать. Если возвращать `forbid` — нужны pass-through поля для `POSTGRES_*`.
2. **`pydantic-settings` priority order.** Установил `monkeypatch.setenv` в тестах, но это означает, что в проде `os.environ` всегда перекрывает `.env`. Согласуем поведение или явно зафиксируем `env_priority` через `customise_sources`?
3. **Тесты-конфига и `.env`.** Сейчас все тесты `monkeypatch.setenv`. Если хочется тестировать сам `.env`-парсинг — нужна отдельная фикстура с `delenv`. Стоит ли её добавлять, или достаточно текущего покрытия?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-004: типизированный конфиг через `pydantic-settings` (`Settings` + `AdminSettings` + `ExternalRegistrySettings`, `SecretStr`-маскировка, валидаторы CSV и http-credentials), structlog с stdlib bridge (`configure_logging`, `get_logger`). 8 unit-тестов. PR [#8](https://github.com/nmetluk/bettgbot/pull/8) → squash. Pre-task cleanup [#7](https://github.com/nmetluk/bettgbot/pull/7) свёл правки cowork (compose layout, dev/compose URLs).
```

## Метрики

- Файлов добавлено: 4 (config.py, logging.py, conftest.py, test_*)
- Файлов изменено: 3 (__init__.py, test_smoke.py, pyproject.toml)
- Тестов добавлено: 8 (config: 5, logging: 3) + 1 обновлён (smoke)
- Покрытие src/shared/: 100% импорт-path; полное функциональное покрытие demand-driven
- Время на выполнение: ~50 мин (включая pre-task cleanup PR и три ruff/mypy-итерации)
