# PROJECT_STATUS

> **Это первое, что читает любой агент или человек в новой сессии.**
> Снапшот должен помещаться в одну прокрутку и отвечать на вопросы: «где мы», «что следующее», «есть ли блокеры».

**Обновлено:** 2026-05-22
**Текущая фаза:** Подготовка инструментария (TASK-002 в работе у cowork).
**Реализация:** инициализация репо завершена; бизнес-код ещё не пишется.

## Где мы сейчас

Bootstrap проекта и инициализация репозитория завершены: структура папок, протоколы handoff и sessions, шаблоны задач/отчётов, инструкции для локального Claude Code, утверждён стек. Удалённый репо `nmetluk/bettgbot` (private) подключён, первый коммит `c3a31ae` запушен в `main`. `gh` + git credential helper настроены на машине владельца (PAT — в macOS Keychain).

Следующая задача — TASK-002: финализация `pyproject.toml`, установка `uv`, генерация lock-файла, pre-commit hooks (ruff + mypy), GitHub Actions CI-stub.

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

## Что в работе прямо сейчас

— ничего, ожидание команды на запуск TASK-002.

## Следующие шаги (короткий горизонт)

1. Владелец даёт команду → локальный Claude Code берёт **TASK-002**: финализация `pyproject.toml`, установка `uv`, lock-файл, pre-commit (ruff + mypy), GitHub Actions CI-stub.
2. После закрытия TASK-002 — TASK-003: `docker-compose.yml` под dev (postgres + redis), entrypoint-скрипты, healthchecks.
3. После TASK-003 — TASK-004: конфиг-слой (`pydantic-settings`, `Settings`) + structlog setup.

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
