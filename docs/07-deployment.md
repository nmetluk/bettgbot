# 07 — Деплой

Один VPS, `docker-compose` управляет всеми сервисами. Подход — простой, воспроизводимый, без оркестраторов.

## Топология

```
┌────────────────────────────────────────────────┐
│ VPS (Ubuntu LTS)                               │
│                                                │
│   nginx  ──TLS──> :80, :443                    │
│     │                                          │
│     └─> /        → web:8000  (admin)           │
│                                                │
│   docker-compose                               │
│   ├─ bot       (long-polling в Telegram API)   │
│   ├─ web       (uvicorn :8000)                 │
│   ├─ db        (postgres:16, volume)           │
│   └─ redis     (redis:7, volume)               │
└────────────────────────────────────────────────┘
```

nginx — на хосте (через apt) или контейнером (на выбор в TASK-026). TLS — Let's Encrypt через certbot.

Telegram — long-polling, не webhook. Проще: не требует публичного HTTPS для самого бота, не нужно настраивать TLS для двух доменов. Если в будущем понадобится — переход на webhook планируется отдельной задачей.

## Раскладка compose-файлов

Принята стандартная для compose v2 трёхфайловая схема (закреплено сессией `2026-05-23-02-task-003-review`, реализуется поэтапно):

| Файл | Сейчас | После TASK-026 (prod-ready) | Когда применяется |
|---|---|---|---|
| `infra/docker-compose.yml` | dev-only: `db` + `redis` | база: `db` + `redis` + `bot` + `web` (без портов наружу) | всегда |
| `infra/docker-compose.override.yml` | — | dev-расширения: проброс `127.0.0.1:5432`, `127.0.0.1:6379`, `bind-mount` `src/` для hot-reload, `restart: "no"` | dev (compose подхватывает автоматически) |
| `infra/docker-compose.prod.yml` | — | prod-расширения: `restart: unless-stopped`, без проброса БД-портов, nginx, prod-логирование | prod (`-f` явно) |

Файл-override **версионируется в репо** (это не secrets), но в `.gitignore` есть отдельный `docker-compose.override.yml` в корне — на случай локальных кастомизаций разработчика, которые не должны попадать в репо.

### Текущая форма (после TASK-003)

`infra/docker-compose.yml` содержит только `db` (postgres:16) и `redis` (redis:7-alpine) — этого достаточно для разработки, пока `bot` и `web` не написаны. Полный файл — в [`infra/docker-compose.yml`](../infra/docker-compose.yml). Поднимается через `Makefile`:

```bash
make up         # docker compose --env-file .env -f infra/docker-compose.yml up -d
make ps         # статус с healthcheck'ами
make db.psql    # psql внутрь контейнера
make redis.cli  # redis-cli
make down       # остановить (данные сохранены)
make nuke       # снести volume'ы (требует ввести NUKE)
```

### Будущая prod-форма (заготовка TASK-026)

После того как появятся `Dockerfile.bot` и `Dockerfile.web` (тоже TASK-026), база `infra/docker-compose.yml` дополнится сервисами `bot` и `web`. Ориентировочно:

```yaml
  bot:
    build:
      context: .
      dockerfile: infra/Dockerfile.bot
    restart: unless-stopped
    env_file: .env
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_healthy }
    command: >
      sh -c "alembic upgrade head && python -m src.bot.main"

  web:
    build:
      context: .
      dockerfile: infra/Dockerfile.web
    restart: unless-stopped
    env_file: .env
    depends_on:
      db: { condition: service_healthy }
    command: >
      sh -c "alembic upgrade head && uvicorn src.admin.app:app --host 0.0.0.0 --port 8000"
```

`alembic upgrade head` запускается в обоих сервисах через `&&`. Гонок не будет — Alembic берёт advisory lock в Postgres. `web` без блока `ports:` в базе — порт наружу пробрасывается nginx-ом, а в dev — через `override.yml`.

`bot` и `web` строятся из `python:3.12-slim` без `pip install` — `COPY src /app/src` + `ENV PYTHONPATH=/app`. Обоснование — [ADR-0004](adr/0004-no-build-backend.md).

## Dockerfile-ы

Два — `Dockerfile.bot` и `Dockerfile.web` — с общим базовым слоем. Слои: `python:3.12-slim` → системные deps → `uv` (или `poetry`) → копия `pyproject.toml` + lock → `uv sync --no-dev` → копия `src/`. Multi-stage по необходимости.

Точные Dockerfile — в TASK-003 (dev) и TASK-026 (prod-ready: non-root user, readonly fs где можно, healthcheck).

## Переменные окружения

`infra/.env.example` (создаётся в TASK-018 одновременно с pyproject):

```
# --- BOT ---
TELEGRAM_BOT_TOKEN=...

# --- DB ---
POSTGRES_USER=betting
POSTGRES_PASSWORD=changeme
POSTGRES_DB=betting
DATABASE_URL=postgresql+asyncpg://betting:changeme@db:5432/betting

# --- REDIS ---
REDIS_URL=redis://redis:6379/0

# --- ADMIN ---
ADMIN_SECRET_KEY=...        # для signed cookie
ADMIN_SESSION_HOURS=8

# --- EXTERNAL REGISTRY ---
EXTERNAL_REGISTRY_BACKEND=mock    # mock | http
EXTERNAL_API_BASE_URL=
EXTERNAL_API_TOKEN=
EXTERNAL_API_TIMEOUT_CONNECT=2.0
EXTERNAL_API_TIMEOUT_READ=5.0

# для mock:
MOCK_REGISTRY_FILE=infra/mock-registry.yml
MOCK_REGISTRY_ALLOWED=

# --- LOGGING ---
LOG_LEVEL=INFO
LOG_FORMAT=json   # json | console

# --- SCHEDULER ---
REMINDER_TICK_SECONDS=300
```

`.env` **не коммитится** (`.gitignore`).

## Бэкапы

- Cron на VPS: ежедневно `pg_dump`, gzip, в `/var/backups/betting/`, ротация 14 дней.
- Опционально — выгрузка дампа в S3-совместимое хранилище. На MVP — локальная директория, обернутая в restic / rsync на отдельный диск.

Скрипт `scripts/backup_db.sh` — в TASK-027.

## Логи

- Контейнеры пишут JSON в stdout/stderr (structlog).
- Docker логи собираются стандартным docker daemon → ротация (`max-size=20m`, `max-file=5`) в `/etc/docker/daemon.json`.
- Для long-term хранения — на MVP достаточно встроенной ротации. Подключение к centralized logging (Loki/ELK) — будущая задача.

## Мониторинг (минимум)

- `docker compose ps` показывает healthchecks.
- Скрипт-проверялка `scripts/check_health.sh` (TASK-026): пинг бота через `getMe`, HTTP-чек `/health` админки, `pg_isready`, `redis-cli ping`. Cron каждые 5 минут; при ошибке — алерт в отдельный служебный чат Telegram.
- Глубже (Prometheus/Grafana) — не на MVP.

## Процедура деплоя

1. `git pull` на VPS в директорию `/opt/bettgbot/`.
2. `docker compose build`.
3. `docker compose up -d`.
4. Дождаться `healthy`.
5. Проверить логи `docker compose logs --tail 100 bot web`.

Автоматизация (GitHub Actions → ssh deploy) — TASK-029 после стабилизации.

## Безопасность VPS (чек-лист, не код)

- SSH — только по ключу, `PasswordAuthentication no`.
- `ufw` пропускает только 22, 80, 443. Порты `8000` и БД — не наружу.
- Регулярный `apt upgrade` (`unattended-upgrades`).
- Все секреты — в `.env` с правами `chmod 600`.
- PAT для git — в `~/.git-credentials` (или через `gh auth login`), не в репо.

## Связанное

- [02-tech-stack.md](02-tech-stack.md), [08-conventions.md](08-conventions.md), [06-external-api.md](06-external-api.md)
