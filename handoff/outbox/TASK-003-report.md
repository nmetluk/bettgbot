---
task: TASK-003
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/5
branch: feature/TASK-003-compose-dev
commits:
  - 3499e5b chore(infra): dev docker-compose stack with postgres + redis
  - 58a3028 chore: add Makefile for compose lifecycle (up/down/logs/ps/psql/redis-cli/nuke)
  - a653828 chore(handoff): mark TASK-003 in-progress
  # squash-merge → e45fa93 на main
---

# Отчёт по TASK-003: Docker Compose для локальной разработки — postgres + redis

## Сводка

Поднялась dev-инфраструктура. `infra/docker-compose.yml` описывает только `db` (postgres:16) и `redis` (redis:7-alpine) — никаких сервисов приложения (это TASK-026). Оба сервиса с healthcheck'ами (`pg_isready`, `redis-cli ping`), `restart: unless-stopped`, именованными volume'ами (`pg_data`, `redis_data`), портами на `127.0.0.1` (не торчат в LAN). `name: bettgbot` фиксирует префикс контейнеров и volume'ов. `POSTGRES_*` подставляются как `${VAR:?...}` — compose падает с понятным сообщением, если `.env` пустой.

`Makefile` в корне репо — единственная команда, нужная разработчику в повседневке: `make help` показывает девять целей, `make up/down/ps/logs/restart` — стандартный CRUD, `make db.psql` и `make redis.cli` — интерактивный shell в контейнер, `make nuke` (с подтверждением `NUKE`) — `down -v` для полного сброса. Цели идемпотентны, POSIX-совместимы (тестировал на macOS make 3.81), все в `.PHONY`.

`infra/.env.example` менять не пришлось — все нужные переменные (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`, `REDIS_URL`) уже были на месте от cowork. Это и отмечено в DoD пункте «оставь как есть».

Перед основной работой сделал pre-task cleanup PR ([#4](https://github.com/nmetluk/bettgbot/pull/4)) с правками cowork: ADR-0004 (формализация `package = false`), сужение CI триггеров `push: branches: [main]`, новый раздел «Pre-task cleanup PR» в `handoff/README.md`, плюс обновления `state/PROJECT_STATUS.md`, `state/DECISIONS.md`, `docs/02-tech-stack.md` и сессия приёмки TASK-002. Получилось чисто: фичевый PR #5 — только три файла про инфру.

## Изменённые файлы

```
+ infra/docker-compose.yml             # новый, 45 строк
+ Makefile                             # новый, 43 строки
  infra/.env.example                   # без изменений (DoD-пункт выполнен)
* handoff/inbox/TASK-003-compose-dev.md → in-progress → archive (этот PR)
+ handoff/archive/TASK-003-compose-dev/task.md
+ handoff/outbox/TASK-003-report.md
```

Никаких файлов в `src/` или `tests/` — задача про инфру, не про код.

## Smoke-проверка локально (реальный вывод)

```text
$ cp infra/.env.example .env
$ make up
docker compose --env-file .env -f infra/docker-compose.yml up -d
 Network bettgbot_default Created
 Volume bettgbot_redis_data Created
 Volume bettgbot_pg_data Created
 Container bettgbot-redis-1 Started
 Container bettgbot-db-1 Started

$ make ps   # ~12 сек после up
NAME               STATUS                    PORTS
bettgbot-db-1      Up 19 seconds (healthy)   127.0.0.1:5432->5432/tcp
bettgbot-redis-1   Up 19 seconds (healthy)   127.0.0.1:6379->6379/tcp

# psql (non-interactive)
$ docker compose ... exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select version();"'
 PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on aarch64-unknown-linux-gnu

# redis
$ docker compose ... exec -T redis sh -c 'redis-cli ping && redis-cli set smoke ok && redis-cli get smoke && redis-cli del smoke'
PONG
OK
ok
1

$ make down
 Container bettgbot-db-1 Removed
 Container bettgbot-redis-1 Removed
 Network bettgbot_default Removed
```

`make ps` после `make down` показывает пустую таблицу. Volume'ы `bettgbot_pg_data` и `bettgbot_redis_data` остаются — снести их можно через `make nuke`.

## Как воспроизвести / запустить

```bash
git checkout main
cp infra/.env.example .env       # отредактируй POSTGRES_PASSWORD если нужно
make up                          # поднять
make ps                          # удостовериться (healthy)
make db.psql                     # → \q для выхода
make redis.cli                   # → quit
make down                        # остановить (данные сохранятся)
# make nuke                      # ОПАСНО: спросит "NUKE" и снесёт volume'ы
```

## Что не сделано / вынесено

- **`make nuke` интерактивно не тестировал** — потребовался бы реальный TTY с вводом `NUKE`. Логика confirmation проверена визуально (`read ans; if [ "$ans" = "NUKE" ]; then ...; else exit 1; fi`). Если cowork хочет автотест — отдельная задача.
- **`docs/07-deployment.md`** содержит черновик compose, который не синхронизирован с моим. Не правил — задача явно запрещает. Замечу: prod-ready compose в TASK-026 будет другим (с `bot`/`web`), так что divergence ожидаем.
- **Smoke-тест на DB-подключение из Python** — не делал, задача запрещает любой Python-код. Реальная проверка коннекта пойдёт в TASK-004 (config layer) или TASK-005 (модели).
- **Healthcheck-агрессивность.** Сейчас `interval: 5s, retries: 10, start_period: 10s` — postgres стартует за ~12с и попадает в healthy. Можно ослабить (`interval: 10s, retries: 5`), но текущие значения дают быструю обратную связь без шторма.

## Открытые вопросы для проектировщика

1. **Структура compose-файлов для prod (TASK-026).** Сейчас один `infra/docker-compose.yml` (dev). Когда придёт prod, варианты:
   - `infra/docker-compose.yml` (база) + `infra/docker-compose.override.yml` (dev-расширения, в gitignore? или в репо?) + явный `-f docker-compose.prod.yml` для прода. Стандартная схема compose.
   - `infra/docker-compose.yml` (dev, как сейчас) + `infra/docker-compose.prod.yml` (отдельно), оба под явный `-f`. Проще читать, но дублирует service-блоки.
   - Я бы предпочёл (a). Подтверди — заверну в TASK-026.
2. **`DATABASE_URL` / `REDIS_URL` в `.env.example`** указывают на имена сервисов compose (`db:5432`, `redis:6379`). Для текущего dev-сценария (приложение запускается с хоста через `uv run`, БД в compose) пользователь должен в `.env` поменять на `localhost:5432` / `localhost:6379`. Стоит ли в этой же задаче дописать в `.env.example` пояснительный комментарий, или это часть TASK-004 (config layer)? Сейчас не правил.
3. **`make nuke` UX.** Подтверждение требует ввести буквы `NUKE`. Альтернативы: `y/yes`, `--force`-флаг, `DELETE`. Если предпочитаешь другое — поменяю в фикс-задаче.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-003: `infra/docker-compose.yml` (postgres:16 + redis:7-alpine, healthchecks, named volumes, 127.0.0.1 bindings); `Makefile` (up/down/logs/ps/psql/redis-cli/nuke). PR [#5](https://github.com/nmetluk/bettgbot/pull/5) → squash `e45fa93`. Pre-task cleanup [#4](https://github.com/nmetluk/bettgbot/pull/4) разнёс правки cowork (ADR-0004, CI триггеры, pre-task pattern).
```

## Метрики

- Файлов добавлено: 2 (compose + Makefile)
- Строк YAML: 45 (compose)
- Make targets: 9 (включая help)
- Smoke-up до healthy: ~19 сек (с тёплым pull)
- Время на выполнение: ~50 мин (включая pre-task cleanup PR)
