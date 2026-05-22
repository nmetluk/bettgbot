# PROJECT_STATUS

> **Это первое, что читает любой агент или человек в новой сессии.**
> Снапшот должен помещаться в одну прокрутку и отвечать на вопросы: «где мы», «что следующее», «есть ли блокеры».

**Обновлено:** 2026-05-23
**Текущая фаза:** Подготовка инфраструктуры разработки.
**Реализация:** инструментарий поднят (uv, pre-commit, CI зелёный); бизнес-код ещё не пишется.

## Где мы сейчас

TASK-001 и TASK-002 закрыты. Репо `nmetluk/bettgbot` готов к разработке: `uv` с lock-файлом, `.pre-commit-config.yaml` (ruff + mypy через `uv run`), GitHub Actions с тремя job'ами (lint/typecheck/test) — все зелёные. Принято архитектурное решение «репо — сервис, не библиотека» (ADR-0004), что повлияет на Dockerfile в TASK-003+. Формализован паттерн pre-task cleanup PR — правки cowork исполнитель упаковывает в отдельный PR перед основной задачей (как было с PR #1 перед TASK-002).

Следующая задача — TASK-003: `infra/docker-compose.yml` с сервисами postgres + redis для локальной разработки, healthchecks, Makefile с командами, smoke-проверка.

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

## Что в работе прямо сейчас

— ничего, ожидание команды на запуск TASK-003.

## Следующие шаги (короткий горизонт)

1. Владелец даёт команду → локальный Claude Code берёт **TASK-003**: `infra/docker-compose.yml` (db + redis), healthchecks, `Makefile`, smoke-проверка.
2. После TASK-003 — TASK-004: конфиг-слой (`pydantic-settings`, `Settings`) + structlog setup.
3. После TASK-004 — TASK-005: ORM-модели всех сущностей по [docs/03-data-model.md](../docs/03-data-model.md).

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
