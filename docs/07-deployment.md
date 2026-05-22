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

## Файл docker-compose.yml (черновик)

Финальный — в TASK-003 и TASK-026. Ориентир:

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "${POSTGRES_USER}"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

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
    ports:
      - "127.0.0.1:8000:8000"
    command: >
      sh -c "alembic upgrade head && uvicorn src.admin.app:app --host 0.0.0.0 --port 8000"

volumes:
  pg_data:
  redis_data:
```

`alembic upgrade head` запускается в обоих сервисах через `&&`. Гонок не будет — Alembic берёт advisory lock в Postgres.

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

1. `git pull` на VPS в директорию `/opt/betting-bot/`.
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
