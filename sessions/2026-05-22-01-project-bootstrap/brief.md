# Brief — project-bootstrap

**Дата:** 2026-05-22
**Длительность:** ~1 сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Новый проект: Telegram-бот для приёма прогнозов на события + минимальная веб-админка. Без биллинга. Регистрация через `Contact` + внешний API проверки. Каждый шаг — отдельная сессия cowork; контекст должен сохраняться между сессиями. Реализация — локальным Claude Code через папку handoff. Проектирование «на высшем профессиональном уровне». Подробная документация. Я (Николай) только даю команды.

## Что планировалось сделать

- Согласовать ключевые архитектурные решения (стек, БД, деплой, внешний API).
- Спроектировать структуру репозитория, поддерживающую двухагентную работу и сохранение контекста.
- Написать полный комплект документации (overview, architecture, data-model, bot-flows, admin-spec, external-api, deployment, conventions).
- Создать протокол handoff и шаблоны задач/отчётов.
- Подготовить первую задачу для локального Claude Code.

## Что фактически сделано

- Согласован стек: Python 3.12 + aiogram 3 + FastAPI + PostgreSQL 16 + Redis + Docker Compose. Mock-адаптер для внешнего API на этапе разработки.
- Создан каркас директорий (`docs/`, `handoff/`, `sessions/`, `state/`, `src/`, `tests/`, `infra/`, `scripts/`, `.github/workflows/`).
- Написаны корневые точки входа: [`README.md`](../../README.md), [`CLAUDE.md`](../../CLAUDE.md).
- Описан handoff-протокол ([`handoff/README.md`](../../handoff/README.md)) и шаблоны ([`handoff/templates/task.md`](../../handoff/templates/task.md), [`report.md`](../../handoff/templates/report.md)).
- Описан формат сессий ([`sessions/README.md`](../README.md)).
- Созданы state-файлы: [`PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md), [`BACKLOG.md`](../../state/BACKLOG.md), [`DECISIONS.md`](../../state/DECISIONS.md), [`GLOSSARY.md`](../../state/GLOSSARY.md).
- Написаны спецификации: [`00-overview.md`](../../docs/00-overview.md), [`01-architecture.md`](../../docs/01-architecture.md), [`02-tech-stack.md`](../../docs/02-tech-stack.md), [`03-data-model.md`](../../docs/03-data-model.md), [`04-bot-flows.md`](../../docs/04-bot-flows.md), [`05-admin-spec.md`](../../docs/05-admin-spec.md), [`06-external-api.md`](../../docs/06-external-api.md), [`07-deployment.md`](../../docs/07-deployment.md), [`08-conventions.md`](../../docs/08-conventions.md).
- ADR: [`0001-tech-stack`](../../docs/adr/0001-tech-stack.md), [`0002-monorepo-layout`](../../docs/adr/0002-monorepo-layout.md), [`0003-handoff-protocol`](../../docs/adr/0003-handoff-protocol.md).
- Базовые конфиги: [`.gitignore`](../../.gitignore), [`pyproject.toml`](../../pyproject.toml) (черновик), [`infra/.env.example`](../../infra/.env.example), [`infra/mock-registry.yml`](../../infra/mock-registry.yml).
- Поставлена первая задача локальному агенту: [`TASK-001-init-repo`](../../handoff/inbox/TASK-001-init-repo.md).

## Что не сделано / отложено

- Финальный выбор пакетного менеджера (uv vs poetry) — на стороне локального агента в TASK-002 (есть рекомендация — uv).
- Финальный выбор Bootstrap-админ-шаблона — в TASK-018.
- Реальный контракт внешнего API — ждёт согласования с владельцем внешней системы; пока контракт-черновик в [`docs/06-external-api.md`](../../docs/06-external-api.md) + mock.
- Конкретный код — не пишем; это зона локального Claude Code по задачам из handoff.

## Следующие шаги

1. **Владелец** даёт команду на запуск TASK-001 (инициализация git + GitHub-репозиторий + первый коммит).
2. **Локальный Claude Code** исполняет TASK-001, выкладывает отчёт в [`handoff/outbox/`](../../handoff/outbox/).
3. **Cowork-агент** в следующей сессии: читает отчёт, обновляет [`PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md), готовит TASK-002 (pyproject.toml + pre-commit + CI-stub).
