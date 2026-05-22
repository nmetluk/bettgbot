# Brief — task-003-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-003 и подготовить следующий шаг.

## Контекст

Локальный агент закрыл TASK-003 чисто: `infra/docker-compose.yml` (postgres:16 + redis:7-alpine, healthchecks, named volumes, bind на 127.0.0.1, `name: bettgbot`), корневой `Makefile` с 9 целями (включая интерактивный `make nuke`), реальный smoke-вывод в отчёте — `psql` и `redis-cli` зелёные за ~19 секунд после `make up`.

Перед основной работой агент сделал pre-task cleanup PR [#4](https://github.com/nmetluk/bettgbot/pull/4) с правками cowork из прошлой сессии (ADR-0004, CI триггеры, абзац про cleanup PR, `docs/02-tech-stack.md`, state-файлы) — паттерн отработал штатно. Основной PR [#5](https://github.com/nmetluk/bettgbot/pull/5) → squash `e45fa93`.

Полный отчёт — [`handoff/outbox/TASK-003-report.md`](../../handoff/outbox/TASK-003-report.md).

## Что сделано в этой сессии

- Принята стратегия compose-файлов: база `infra/docker-compose.yml` + `infra/docker-compose.override.yml` (dev, в репо) + `infra/docker-compose.prod.yml` (явный `-f`). Реализуется поэтапно — текущая база уже на месте, остальное в TASK-026.
- [`docs/07-deployment.md`](../../docs/07-deployment.md) переписан: убран старый «черновик compose», добавлена таблица раскладки файлов, текущая форма со ссылкой на реальный файл, заготовка будущей формы (bot/web) с пояснением про `PYTHONPATH=/app` со ссылкой на ADR-0004.
- [`infra/.env.example`](../../infra/.env.example) дополнен двумя вариантами `DATABASE_URL` и `REDIS_URL` (localhost для dev, compose-имена для compose-сценария). По умолчанию активен dev.
- `make nuke` оставлен с подтверждением через ввод `NUKE` — зафиксировано в [`DECISIONS.md`](../../state/DECISIONS.md).
- Обновлены [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (TASK-003 закрыт, следующий — TASK-004) и [`state/DECISIONS.md`](../../state/DECISIONS.md) (три новые записи).
- Сформирована задача [`handoff/inbox/TASK-004-config-logging.md`](../../handoff/inbox/TASK-004-config-logging.md) (`pydantic-settings` + `structlog`).

## Что не сделано / отложено

- **Структура prod-compose с bot/web сервисами** — реальные файлы `Dockerfile.bot`/`Dockerfile.web`/`override.yml`/`prod.yml` появятся в TASK-026, когда у нас будет код бота и админки. Сейчас зафиксирована только стратегия в `docs/07`.
- **Тест `make nuke`** — не запускается из CI (требует TTY с интерактивным вводом). Если решим — отдельная задача.

## Следующие шаги

1. Владелец запускает локальный Claude Code на TASK-004.
2. Локальный агент сначала делает pre-task cleanup PR с правками этой сессии (`.env.example`, `docs/07-deployment.md`, state-файлы, новая сессия), мёрджит, потом начинает TASK-004 на свежем `main`.
3. После TASK-004 — TASK-005 (ORM-модели).
