# PROJECT_STATUS

> **Это первое, что читает любой агент или человек в новой сессии.**
> Снапшот должен помещаться в одну прокрутку и отвечать на вопросы: «где мы», «что следующее», «есть ли блокеры».

**Обновлено:** 2026-05-23
**Текущая фаза:** Доменный слой готов целиком. Следующее — Telegram-бот (aiogram bootstrap).
**Реализация:** runtime + конфиг + логгер + модели + миграция + engine + репозитории + внешний реестр + 6 сервисов; 109 тестов; CI 4 зелёных job'а.

## Где мы сейчас

TASK-001 — TASK-009 закрыты. Полный комплект «средний этаж + ниже»: `src/shared/services/` — `UserService` (с инъекцией `ExternalUserRegistryClient`), `EventService` (transactional `set_result`: update + `mark_correctness` + audit), `PredictionService` (валидация дедлайна/архива/исхода), `ReminderService` (валидация offsets), `StatsService`, `AuditService`. Доменные исключения в `src/shared/exceptions.py` (13 классов под `DomainError`). Все write-методы сервисов сами коммитят; rollback — работа контекст-менеджера сессии (зафиксировано в [`docs/08-conventions.md`](../docs/08-conventions.md)). Step 0 TASK-009 применил две правки TASK-008 (shared `X-Request-Id`, `@lru_cache` на фабрике registry).

По итогам review TASK-009 согласована одна минорная правка кода (убрать `rollback()` из `EventService.delete_outcome` — сессия сама откатит) — встроена в Step 0 TASK-010 вместе с комментарием про session vs nested_session фикстуры. Следующая задача — TASK-010: скелет aiogram-приложения (dispatcher, RedisStorage для FSM, middleware с `get_session` и `touch_last_seen`, пустые router-стабы, тексты, клавиатуры).

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
- 2026-05-23 — **TASK-005 закрыт:** 8 ORM-моделей в `src/shared/models/` по `docs/03-data-model.md`, `Base` с naming convention и `type_annotation_map`, циклика `Event ↔ Outcome` через `use_alter`, partial-index `ix_event_predictions_close_at_active`, CHECK на инвариантах события. 13 unit-тестов (metadata + relationships). PR [#11](https://github.com/nmetluk/bettgbot/pull/11) → squash `0984fbb`; pre-task cleanup PR [#10](https://github.com/nmetluk/bettgbot/pull/10)
- 2026-05-23 — сессия приёмки `2026-05-23-04-task-005-review`; согласованы три tweaks (NOT NULL `metadata_`, `String(128) full_name`, unified `ck`-convention) — встроены в DoD TASK-006; оставлены без изменений `Prediction.is_correct` server_default и `CASCADE` на `Outcome.event_id`
- 2026-05-23 — **TASK-006 закрыт:** 3 model tweaks + `src/shared/db.py` (async engine + sessionmaker + get_session) + Alembic async-env (читает URL из `Settings`) + миграция `0001_init.py` (8 таблиц, 24 индекса, partial-index, CHECK, циклическая FK через `op.create_foreign_key`+`use_alter`) + 6 Makefile-целей + новый CI job `integration` (postgres:16 service, 4 теста через `pg_tables`/`pg_indexes`/`pg_constraint`). 22 unit + 4 integration зелёные. PR [#14](https://github.com/nmetluk/bettgbot/pull/14) → squash `fdddac9`; pre-task cleanup PR [#13](https://github.com/nmetluk/bettgbot/pull/13)
- 2026-05-23 — сессия приёмки `2026-05-23-05-task-006-review`; зафиксированы 5 решений (split `tests/unit/conftest.py`, subprocess `alembic` в integration, module-level engine, мини-`_load_dotenv`, без teardown postgres-service); BACKLOG скорректирован — repos и services разделены на TASK-007 и TASK-008
- 2026-05-23 — **TASK-007 закрыт:** 8 репозиториев в `src/shared/repositories/` (тонкий query-слой, ~750 строк), 37 integration-тестов на реальный Postgres (per-test engine + NullPool для обхода pytest-asyncio event-loop изоляции), `pg_insert + on_conflict_do_update + refresh()` для upsert, `update + case` для `mark_correctness`. CI unit job сужен до `tests/unit/`. PR [#17](https://github.com/nmetluk/bettgbot/pull/17) → squash `6815666`; pre-task cleanup PR [#16](https://github.com/nmetluk/bettgbot/pull/16)
- 2026-05-23 — сессия приёмки `2026-05-23-06-task-007-review`; зафиксированы 5 решений по review (оставлены как есть: per-test engine, refresh после upsert, сужение unit job, `metadata_={}` в `EventRepository.create`, `list_with_admin` отложен до TASK-026); порядок TASK-008/TASK-009 переставлен: registry → services
- 2026-05-23 — **TASK-008 закрыт:** в `src/shared/external/` собран комплект (registry.py: Protocol/VerificationResult/ExternalApiError; mock_registry.py: YAML + env CSV; http_registry.py: httpx + retry с backoff, sha256-маска phone в logs; `__init__.py`: фабрика `get_registry_client()`). 19 unit-тестов (7 mock + 10 http через `httpx.MockTransport` + 2 factory). PR [#20](https://github.com/nmetluk/bettgbot/pull/20) → squash `618a431`; pre-task cleanup PR [#19](https://github.com/nmetluk/bettgbot/pull/19)
- 2026-05-23 — сессия приёмки `2026-05-23-07-task-008-review`; зафиксированы 5 решений (shared `X-Request-Id` для всех попыток одного verify + `@lru_cache` на фабрике — встроены в Step 0 TASK-009; оставлены без изменений defensive YAML parsing, глобальный `random` для fail_rate, `client: AsyncClient | None` параметр)
- 2026-05-23 — **TASK-009 закрыт:** 6 сервисов в `src/shared/services/` + `src/shared/exceptions.py` (13 классов под `DomainError`); transactional `EventService.set_result` (update + mark_correctness + audit); `UserService` с инъекцией `ExternalUserRegistryClient`. 31 integration-тест на nested-savepoint фикстуре (SAVEPOINT для сервисного commit). Step 0: shared `X-Request-Id` + `@lru_cache` на registry. PR [#23](https://github.com/nmetluk/bettgbot/pull/23) → squash `b102b9e`; pre-task cleanup PR [#22](https://github.com/nmetluk/bettgbot/pull/22)
- 2026-05-23 — сессия приёмки `2026-05-23-08-task-009-review`; зафиксированы 5 решений (правило импортов внешних модулей дописано в `docs/08-conventions.md`; убрать `rollback()` из `EventService.delete_outcome` встроено в Step 0 TASK-010; оставлены — оба fixture'а раздельно, `touch_last_seen` коммитит, `StubRegistry` в services conftest)

## Что в работе прямо сейчас

— ничего, ожидание команды на запуск TASK-010.

## Следующие шаги (короткий горизонт)

1. Владелец даёт команду → локальный Claude Code берёт **TASK-010**: Step 0 (две правки TASK-009) → aiogram bootstrap (`src/bot/main.py`, `src/bot/middlewares/{logging,session}.py`, `src/bot/routers/*` пустые стабы, `src/bot/keyboards/`, `src/bot/states.py`, `src/bot/texts.py`); RedisStorage для FSM; unit-тесты middleware.
2. После TASK-010 — TASK-011: `/start` + регистрация через `Contact` + вызов `UserService.register_or_authenticate`.
3. После TASK-011 — TASK-012: команда «Все события» с пагинацией и фильтром по категории.

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
