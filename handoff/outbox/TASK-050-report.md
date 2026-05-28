# TASK-050 Report: Per-service env segregation

## Что сделано

### 1. Созданы per-service `.env.example` файлы

- `infra/.env.bot.example` — переменные для bot-сервиса
- `infra/.env.web.example` — переменные для web-сервиса (admin panel)
- `infra/.env.db.example` — переменные для db/db-backup сервисов

Эти файлы служат документацией минимального набора переменных для каждого сервиса.

### 2. Обновлены docker-compose конфигурации

Заменён `env_file: ../.env` на явные `environment:` блоки с перечислением конкретных переменных:

**`infra/docker-compose.yml` (base):**
- `bot`: получает `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`, переменные external registry
- `web`: получает `DATABASE_URL`, `REDIS_URL`, `ADMIN_SECRET_KEY`, `ADMIN_CSRF_SECRET`
- Убрана кросс-экспозиция секретов между сервисами

**`infra/docker-compose.prod.yml`:**
- `db-backup`: получает только `POSTGRES_*` и `BACKUP_*` переменные
- Больше НЕ получает `TELEGRAM_BOT_TOKEN`, `ADMIN_SECRET_KEY`, `ADMIN_CSRF_SECRET`

**`infra/docker-compose.prod-no-domain.yml`:**
- `db-backup`: аналогично, только `POSTGRES_*` переменные

**`infra/docker-compose.override.yml`:**
- Изменений не требовалось (нет `env_file`, inherits from base)

### 3. Обновлена документация

**`docs/07-deployment.md`:**
- Добавлен раздел "Сегрегация секретов по сервисам"
- Описан подход с явными `environment:` блоками вместо `env_file:`
- Ссылки на per-service `.env.example` файлы

### 4. Верификация

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Проверено через `docker compose config`:
- ✅ `bot` НЕ имеет `ADMIN_SECRET_KEY`, `ADMIN_CSRF_SECRET`
- ✅ `web` НЕ имеет `TELEGRAM_BOT_TOKEN`
- ✅ `db-backup` имеет только `POSTGRES_*` и `BACKUP_*`, НЕ имеет `TELEGRAM_BOT_TOKEN` или admin secrets

## Diff-сводка

```
infra/docker-compose.yml              | env_file → environment block (bot, web)
infra/docker-compose.prod.yml         | env_file → environment block (db-backup)
infra/docker-compose.prod-no-domain.yml| env_file → environment block (db-backup)
docs/07-deployment.md                 | added segregation docs
infra/.env.bot.example                | NEW
infra/.env.web.example                | NEW
infra/.env.db.example                 | NEW
```

## Что не сделано

Ничего — все пункты DoD выполнены.

## Открытые вопросы

Нет.

## Команды для воспроизведения

```bash
# Проверить конфигурацию (потребуется .env файл):
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config

# Проверить env переменные конкретного сервиса:
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config | grep -A 30 "db-backup:"

# Smoke-проверка запуска:
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d db
```

## Следующие шаги

Слияние PR в `main` после ревью. TASK-034 (валидация секретов на старте) обеспечит отказ при неполном `.env`.

---

**Артефакты для коммита:**
- `infra/docker-compose.yml`
- `infra/docker-compose.prod.yml`
- `infra/docker-compose.prod-no-domain.yml`
- `docs/07-deployment.md`
- `infra/.env.bot.example`
- `infra/.env.web.example`
- `infra/.env.db.example`
