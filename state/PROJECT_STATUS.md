# PROJECT_STATUS

> **Это первое, что читает любой агент или человек в новой сессии.**
> Снапшот должен помещаться в одну прокрутку и отвечать на вопросы: «где мы», «что следующее», «есть ли блокеры».

**Обновлено:** 2026-05-23
**Текущая фаза:** Бизнес-код. Стартует доменный слой (модели).
**Реализация:** runtime-инфра (`make up`), типизированный конфиг (`src/shared/config.py`), structlog (`src/shared/logging.py`); 9 unit-тестов, CI зелёный.

## Где мы сейчас

TASK-001 / TASK-002 / TASK-003 / TASK-004 закрыты. Помимо инфры в репо теперь живёт типизированный `Settings` (вложенные `AdminSettings`, `ExternalRegistrySettings`; `SecretStr`-маскировка; валидаторы CSV и http-credentials) и единый структурный логгер (JSON/console по `LOG_FORMAT`, stdlib bridge для логов aiogram/sqlalchemy/uvicorn). `conftest.py` со stub-env позволяет тестам импортировать `src.shared` без реального `.env`. Дальше — доменный слой.

Следующая задача — TASK-005: ORM-модели всех сущностей по [docs/03-data-model.md](../docs/03-data-model.md), индексы, CHECK constraints, relationships, unit-тесты на метаданные.

## Что готово

- 2026-05-22 — каркас директорий, [README.md](../README.md), [CLAUDE.md](../CLAUDE.md)
- 2026-05-22 — протокол handoff: [handoff/README.md](../handoff/README.md), шаблоны
- 2026-05-22 — журнал сессий: [sessions/README.md](../sessions/README.md), сессия `2026-05-22-01-project-bootstrap`
- 2026-05-22 — state-файлы: PROJECT_STATUS, BACKLOG, DECISIONS, GLOSSARY
- 2026-05-22 — спецификации в `docs/`: 00-overview, 01-architecture, 02-tech-stack, 03-data-model, 04-bot-flows, 05-admin-spec, 06-external-api, 07-deployment, 08-conventions
- 2026-05-22 — ADR-0001 (tech stack), ADR-0002 (monorepo layout), ADR-0003 (handoff protocol)
- 2026-05-22 — `.gitignore`, `.env.example`, `pyproject.toml`-заготовка
- 2026-05-22 — **TASK-001 закрыт:** git-репо инициализирован, root-commit `c3a31ae` в `nmetluk/bettgbot` (private); `gh` + git credential helper настроены; PR-template добавлен. Branch protection отложен (GitHub free не поддерживает для private — см. [DECISIONS.md](DECISIONS.md))
- 2026-05-22 — сессия приёмки `2026-05-22-02-task-001-review`; имя репо унифицировано на `bettgbot` во всех документах
- 2026-05-23 — **TASK-002 закрыт:** `pyproject.toml` финализирован, `uv.lock` сгенерирован, `__init__.py` в `src/{shared,bot,admin}`, smoke-тест, `.pre-commit-config.yaml` (ruff + mypy через `uv run`), `.github/workflows/ci.yml` (lint/typecheck/test — все зелёные). PR [#2](https://github.com/nmetluk/bettgbot/pull/2) → squash `bb89808`. Принят [ADR-0004](../docs/adr/0004-no-build-backend.md) (нет build-backend, `package = false`)
- 2026-05-23 — сессия приёмки `2026-05-23-01-task-002-review`; формализован [pre-task cleanup PR](../handoff/README.md#pre-task-cleanup-pr); CI триггеры сужены до `push: [main]` + `pull_request`
- 2026-05-23 — **TASK-003 закрыт:** `infra/docker-compose.yml` (postgres:16 + redis:7-alpine, healthchecks, named volumes, 127.0.0.1 bindings, `name: bettgbot`), корневой `Makefile` (9 целей с `make help`), smoke-проверка `psql` + `redis-cli` зелёная. PR [#5](https://github.com/nmetluk/bettgbot/pull/5) → squash `e45fa93`; pre-task cleanup PR [#4](https://github.com/nmetluk/bettgbot/pull/4)
- 2026-05-23 — сессия приёмки `2026-05-23-02-task-003-review`; принята стратегия compose (база + override.yml + prod.yml); `.env.example` дополнен dev/compose вариантами URL; `docs/07-deployment.md` обновлён под текущую и будущую форму
- 2026-05-23 — **TASK-004 закрыт:** типизированный конфиг через `pydantic-settings` (`Settings` + `AdminSettings` + `ExternalRegistrySettings`, `SecretStr`-маскировка, CSV-парсер, валидатор «http backend → token»), structlog с stdlib bridge (`configure_logging`, `get_logger`). `conftest.py` stub-env. 8 unit-тестов. PR [#8](https://github.com/nmetluk/bettgbot/pull/8); pre-task cleanup PR [#7](https://github.com/nmetluk/bettgbot/pull/7)
- 2026-05-23 — сессия приёмки `2026-05-23-03-task-004-review`; зафиксировано `extra="ignore"` (а не `forbid`), `monkeypatch.setenv` как стиль тестов, env > .env как штатный приоритет

## Что в работе прямо сейчас

— ничего, ожидание команды на запуск TASK-005.

## Следующие шаги (короткий горизонт)

1. Владелец даёт команду → локальный Claude Code берёт **TASK-005**: ORM-модели восьми сущностей в `src/shared/models/` (User, Category, Event, Outcome, Prediction, ReminderSetting, AdminUser, AuditLog), индексы, CHECK constraints, relationships; unit-тесты на metadata.
2. После TASK-005 — TASK-006: `src/shared/db.py` (async engine + sessionmaker) + Alembic + первая миграция `0001_init`, прогоняемая на пустой БД из compose.
3. После TASK-006 — TASK-007: репозитории (`UserRepository`, `EventRepository`, `PredictionRepository`, `AuditRepository`) — тонкий слой запросов.

## Блокеры / открытые вопросы

- **Контракт внешнего API** — на этапе разработки используется mock-адаптер; реальный API ждёт согласования с владельцем внешней системы. См. [docs/06-external-api.md](../docs/06-external-api.md).
- **Branch protection** — отложен по решению владельца (см. [DECISIONS.md](DECISIONS.md)); митигация — дисциплина workflow (только ветки + PR через handoff).

## Куда смотреть дальше

- [BACKLOG.md](BACKLOG.md) — приоритизированный список задач за горизонтом ближайших.
- [DECISIONS.md](DECISIONS.md) — журнал решений.
- [GLOSSARY.md](GLOSSARY.md) — словарь предметной области.
- [../docs/](../docs/) — все спецификации.
- [../sessions/](../sessions/) — история проектирования.
- [../handoff/](../handoff/) — поток задач исполнителю.
