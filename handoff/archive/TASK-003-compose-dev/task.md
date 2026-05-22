---
id: TASK-003
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/07-deployment.md
  - docs/02-tech-stack.md
  - infra/.env.example
priority: high
estimate: M
---

# TASK-003: Docker Compose для локальной разработки — postgres + redis

## Контекст

После TASK-002 у нас есть рабочий Python-репо с CI, но ни одной запущенной runtime-зависимости. Чтобы дальнейшие задачи (TASK-004 конфиг, TASK-005 модели, TASK-006 первая миграция, TASK-007 сервисы) могли локально подниматься и прогоняться против реальных БД и Redis — нужен dev-вариант `docker-compose.yml`.

В этой задаче поднимаем **только инфраструктурные сервисы** (postgres + redis). Контейнеры `bot` и `web` придут позже (TASK-026, prod-ready compose). Сейчас разработчик и тесты будут подключаться к `localhost:5432` / `localhost:6379` напрямую из хоста.

Архитектурный контекст — [docs/07-deployment.md](../../docs/07-deployment.md) (раздел «Файл docker-compose.yml (черновик)»). Все настройки берутся из [infra/.env.example](../../infra/.env.example).

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь рабочее дерево и `origin/main` на накопленные правки от cowork ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку этой задачи такие правки есть (ADR-0004, обновлённые `docs/02-tech-stack.md` / `state/PROJECT_STATUS.md` / `state/DECISIONS.md` / `handoff/README.md`, изменения в `.github/workflows/ci.yml`). Упакуй их в `chore/post-TASK-002-cowork-cleanup`, открой PR, замерджи в `main`. Только после этого создавай `feature/TASK-003-compose-dev` от свежего main.

## Цель

В репозитории есть `infra/docker-compose.yml`, которым одной командой поднимаются и опускаются postgres + redis с пробросом портов на хост, healthchecks и именованными volume'ами. Есть `Makefile` (или Justfile — на выбор) с удобными командами для повседневной работы.

## Definition of Done

- [ ] `infra/docker-compose.yml` создан и содержит:
  - сервис `db` — образ `postgres:16`, `restart: unless-stopped`, env из `.env`, named volume `pg_data`, healthcheck (`pg_isready -U $POSTGRES_USER -d $POSTGRES_DB`), порт `127.0.0.1:5432:5432` (биндинг на loopback, **не** на 0.0.0.0)
  - сервис `redis` — `redis:7-alpine`, `restart: unless-stopped`, named volume `redis_data`, healthcheck (`redis-cli ping`), порт `127.0.0.1:6379:6379`
  - секция `volumes:` с обоими тома́ми
  - **без** сервисов `bot` и `web` (это TASK-026)
- [ ] `infra/.env.example` дополнен любыми отсутствующими переменными, если они нужны compose-у (например, `POSTGRES_INITDB_ARGS` — если решишь использовать). Если правок не нужно — оставь как есть и отметь в отчёте.
- [ ] Создан `Makefile` в корне репо с целями (минимум):
  - `make help` — список целей с описанием
  - `make up` — `docker compose --env-file .env -f infra/docker-compose.yml up -d`
  - `make down` — `docker compose ... down`
  - `make logs` — `docker compose ... logs -f`
  - `make ps` — статус сервисов
  - `make db.psql` — `docker compose ... exec db psql -U $POSTGRES_USER $POSTGRES_DB`
  - `make redis.cli` — `docker compose ... exec redis redis-cli`
  - `make nuke` — `down -v` (с подтверждением через `@read` или `confirm:` цель — удаляет volume'ы; это опасно, поэтому отдельная цель)
- [ ] `Makefile` использует `.PHONY` для всех целей; цели идемпотентны.
- [ ] Smoke-проверка выполнена локально: `cp infra/.env.example .env` (с заполнением `POSTGRES_*` дефолтными значениями) → `make up` → `make ps` показывает `healthy` для обоих сервисов → `make db.psql` пускает в psql → `make redis.cli` пускает в redis-cli → `make down`. Шаги и реальный вывод приложи к отчёту.
- [ ] В `.gitignore` уже есть `.env` и `docker-compose.override.yml` — проверь, что они **не** коммитятся.
- [ ] Ничего не добавлено в `src/` или `tests/` (эта задача — про инфру, не про код).
- [ ] Ветка `feature/TASK-003-compose-dev`, коммиты Conventional, PR в `main` открыт, CI зелёный.
- [ ] Отчёт `handoff/outbox/TASK-003-report.md` написан.
- [ ] Задача перемещена в `handoff/archive/TASK-003-compose-dev/task.md`.

## Артефакты

```
+ infra/docker-compose.yml             # новый
* infra/.env.example                   # возможно, добавятся переменные
+ Makefile                             # новый
```

## Ссылки

- [docs/07-deployment.md](../../docs/07-deployment.md) — черновик docker-compose, который сейчас обогащаешь
- [infra/.env.example](../../infra/.env.example) — переменные окружения
- [ADR-0004](../../docs/adr/0004-no-build-backend.md) — почему bot/web сервисы не будут использовать `pip install`

## Подсказки исполнителю

- **Биндинг на 127.0.0.1, не 0.0.0.0.** На VPS позже мы будем держать порты внутри compose-сети, наружу выпускать только nginx. Сейчас, для локальной разработки, привязка к loopback закроет порт от случайного публичного доступа на разработческой машине.
- **Healthcheck postgres**: `test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]` — двойной доллар, чтобы compose не подставил пустые значения, а оставил переменные оболочки для контейнера. `interval: 5s`, `timeout: 5s`, `retries: 10`, `start_period: 10s`.
- **Healthcheck redis**: `test: ["CMD", "redis-cli", "ping"]`. Минимум зависимостей.
- **Версия compose-файла**: можно не указывать `version:` — современный compose v2 не требует и даже жалуется. Если поставишь — фиксируй `version: "3.9"` максимум.
- **Имя проекта compose**: по умолчанию compose возьмёт имя директории (`bettg-bot` или `Betting Bot` с очисткой). Лучше явно — `name: bettgbot` в верхней части YAML; это даст предсказуемые имена контейнеров (`bettgbot-db-1`, `bettgbot-redis-1`) и volume'ов (`bettgbot_pg_data`).
- **Расположение compose-файла.** В TASK-026 (prod-ready) появится либо второй файл, либо тот же расширится override'ом. Структура `infra/docker-compose.yml` (dev) + позже `infra/docker-compose.prod.yml` (prod) — норм; явно зафиксируешь в отчёте.
- **Makefile-каверзы**: на macOS дефолтный Make старый (3.81). Используй POSIX-совместимые конструкции. Цвета и `@` (silent) приветствуются. Пример `help`:
  ```makefile
  help: ## Показать доступные команды
  	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_.-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
  ```
- **Логи `docker compose`** vs `docker-compose`. Используй `docker compose` (v2, плагин). Если на машине только v1 — сообщи в отчёте; не пытайся ставить v2 в рамках задачи.

## Что НЕ делать

- Не добавлять сервисы `bot`, `web`, `nginx` — это **TASK-026**, эта задача только про dev-инфру.
- Не настраивать Alembic, миграции, не подключать SQLAlchemy — это **TASK-006**.
- Не писать никакого Python-кода (даже smoke-теста подключения).
- Не править `docs/07-deployment.md` — финальный compose в нём опишет другая задача, когда дойдём до prod-ready compose. Если хочется зафиксировать наблюдения — пиши в отчёт, cowork решит, где это место.
- Не открывать публичные порты (никаких `0.0.0.0:`).
- Не коммитить `.env` (только `.env.example`).
