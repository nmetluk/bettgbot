---
id: TASK-030
created: 2026-05-25
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/shared/logging.py
  - src/shared/config.py
  - docs/07-deployment.md
priority: normal
estimate: M
---

# TASK-030: Structured JSON logging + log rotation для prod

## Контекст

Текущая логгер-конфигурация в `src/shared/logging.py` (TASK-004) — `structlog` с stdlib-bridge, человеко-читаемый `ConsoleRenderer`. Это удобно для dev, но для prod-эксплуатации нужны:

1. **JSON-формат** — чтобы строки парсились логанализаторами (`jq`, `lnav`, Promtail/Loki, `docker logs --format`) и фильтрация по полям (request_id, user_id, level) работала из коробки.
2. **Log rotation** — без неё стандартный stdout-логгинг в Docker'е растёт неограниченно. Если ротация уже задана на уровне Docker daemon json-file driver (см. TASK-027 `infra/docker-compose.prod.yml`: bot/web имеют `logging.driver=json-file, options.max-size=10m, max-file=3`), то это покрывает базу — но при выходе за пределы json-file (например в файл на хосте, на S3, в Sentry) нужна **TimedRotatingFileHandler** или эквивалент.

После TASK-030 в Этапе 4 остаётся: TASK-031 (Deploy README) и TASK-032 (smoke-тесты после деплоя). MVP завершён после TASK-032.

## Цель

В prod-окружении бот и админка должны логировать в JSON-формате со стабильным набором полей. Dev-окружение остаётся с человеко-читаемым выводом. Переключение — через единственный env `LOG_FORMAT` (`json` | `console`), значение по умолчанию = `console`.

## Definition of Done

- [ ] **`src/shared/config.py`:** добавлено поле `Settings.log_format: Literal["json", "console"] = "console"`. С env-биндингом `LOG_FORMAT`. Документировано в `Settings` docstring + в `infra/.env.example`.
- [ ] **`src/shared/logging.py`:** `configure_logging(settings)` (или эквивалент) **читает `settings.log_format`** и:
  - При `console` — `ConsoleRenderer(colors=True)` (текущее поведение, без регрессии для dev).
  - При `json` — `structlog.processors.JSONRenderer()`. Также добавить `EventRenamer("message")` и `TimeStamper(fmt="iso", utc=True)` если их ещё нет. Stdlib `logging.Formatter` тоже должен выдавать JSON (через `structlog.stdlib.ProcessorFormatter` с тем же `JSONRenderer`).
- [ ] **Поля JSON-лога (минимум):** `timestamp` (ISO8601 UTC), `level`, `logger` (имя модуля), `event` (или `message`), `request_id` (если есть в `contextvars` — берётся автоматически благодаря `structlog.contextvars.merge_contextvars`).
- [ ] **`infra/.env.example`:** новая строка `LOG_FORMAT=console` с комментарием «`console` для dev (читаемо), `json` для prod (парсится `jq`/Loki/etc.)».
- [ ] **`infra/docker-compose.prod.yml`:** для сервисов bot и web добавить `environment: LOG_FORMAT: json` (на уровне сервиса, не env_file — чтобы переопределить дефолт `console` из `.env`). Альтернатива — пометить в .env что для prod надо ставить вручную; **более чистый путь** — override на сервисе.
- [ ] **Unit-тест** `tests/unit/test_logging.py` (или дополнение к существующему): два кейса — `log_format="console"` → `ConsoleRenderer` в processor chain, `log_format="json"` → `JSONRenderer`. Не нужно проверять реальный output (это тестировал бы сам structlog) — достаточно проверить, что нужный processor сидит в `structlog.get_config()["processors"]`.
- [ ] **Smoke на dev-stack:**
  - `LOG_FORMAT=console make admin` → лог как сейчас (человеко-читаемый).
  - `LOG_FORMAT=json make admin` → строки лога — валидный JSON, проверяется `... | jq .` без ошибок.
- [ ] PR/коммит conventional, одна ветка.
- [ ] `handoff/outbox/TASK-030-report.md` с **прогоном обоих smoke-тестов** (показать пример строки в обоих форматах). Не забыть `git rm` обе копии TASK-030 в inbox после move в archive (см. `handoff/README.md` подсекция «Move-семантика inbox → archive»).
- [ ] `make backup` после merge в main (DoD CLAUDE.md п.5.5).

## Артефакты

- `* src/shared/config.py` — поле `log_format: Literal["json", "console"]`
- `* src/shared/logging.py` — branch по `settings.log_format`
- `+ tests/unit/test_logging.py` (или дополнение к существующему `test_logging.py` / `test_config.py`)
- `* infra/.env.example` — новый env `LOG_FORMAT`
- `* infra/docker-compose.prod.yml` — `environment: LOG_FORMAT: json` для bot и web
- `+ handoff/outbox/TASK-030-report.md`

## Подсказки исполнителю

### structlog processor chain (рекомендуемая конфигурация для prod)

```python
processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.dev.set_exc_info,
    structlog.processors.format_exc_info,
]
if settings.log_format == "json":
    processors.append(structlog.processors.JSONRenderer())
else:
    processors.append(structlog.dev.ConsoleRenderer(colors=True))
structlog.configure(processors=processors, ...)
```

И аналогично для `structlog.stdlib.ProcessorFormatter` который применяется к stdlib-логгерам (aiogram, sqlalchemy, uvicorn) — чтобы их строки тоже шли в JSON, а не оставались text'ом.

### Уровни логирования (не меняем сейчас)

Текущая `LOG_LEVEL` env (если есть в Settings) остаётся как есть. Не вводи новые уровни — задача про **формат**, не про verbosity.

### Не делай

- Не пиши в файл напрямую через `TimedRotatingFileHandler` — Docker'овский `json-file` driver с `max-size/max-file` (уже задан в `infra/docker-compose.prod.yml` для bot/web) даёт ротацию на уровне инфры. Дублировать на уровне приложения — лишний код.
- Не используй `python-json-logger` или альтернативные библиотеки — `structlog.processors.JSONRenderer` родной для нашего стека.
- Не трогай `pyproject.toml`/зависимости — `structlog` уже есть с TASK-004.

### Ловушки

1. **stdlib-логгеры (aiogram, sqlalchemy, uvicorn) не пройдут через structlog automatically.** Нужно `logging.basicConfig(handlers=[handler])` где у `handler.formatter` — `ProcessorFormatter` с теми же processors. Иначе uvicorn будет писать в plain text параллельно с JSON-выводом structlog.
2. **`TimeStamper(utc=True)`** — обязательно UTC, иначе при коллекции с разных серверов будут разные TZ.
3. **`merge_contextvars`** должен быть **первым** в chain, иначе `request_id` не попадёт в финальный JSON-вывод.

## Ссылки

- Текущий logging-setup: [`src/shared/logging.py`](../../src/shared/logging.py)
- Settings: [`src/shared/config.py`](../../src/shared/config.py)
- Docker json-file ротация: [`infra/docker-compose.prod.yml`](../../infra/docker-compose.prod.yml) (секция `logging` у bot/web)
- structlog docs: https://www.structlog.org/en/stable/processors.html

## Что НЕ делать

- Не настраивать внешний log aggregator (Loki/ELK/Datadog) — за MVP. JSON-формат подготавливает почву для будущего, не требует здесь и сейчас.
- Не трогать Sentry/error-tracker — отдельная задача за MVP.
- Не менять log levels или verbosity — только формат вывода.

**Размер:** M (2-3 часа с тестами).
