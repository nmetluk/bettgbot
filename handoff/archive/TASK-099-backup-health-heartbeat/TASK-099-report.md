---
task: TASK-099
completed: 2026-06-02
agent: claude-code-local
status: done
pr: TBD
branch: feature/TASK-099-backup-health-heartbeat
commits:
  - feat: TASK-099 backup health heartbeat - core foundation
  - feat: TASK-099 implement job and db-backup instrumentation
---

# Отчёт по TASK-099: Backup health heartbeat внутри бота (через таблицу backup_run)

## Сводка

Реализован внутренний мониторинг здоровья бэкапов по паттерну TASK-097.

- Добавлена таблица `backup_run` (миграция 0008).
- `BackupRunRepository` с методами чтения последнего успешного и последнего бэкапа.
- `send_backup_health_heartbeat` — ежечасный джоб (Cron :07), читает `backup_run`, проверяет видимость Postgres/Redis, шлёт OK/ALERT в ADMIN_TELEGRAM_CHAT_IDS.
- Условная регистрация джоба (только если `BACKUP_HEARTBEAT_ENABLED=true`).
- Инструментирован `db-backup` контейнер (запись `running` → `success/failed` + размер/ошибка через psql).
- Тексты вынесены в `texts.py`.
- Флаги добавлены в Settings и compose.

Вся бизнес-логика — в сервисе/репозитории, джоб только оркестрирует и форматирует.

## Изменённые файлы (основные)

```
+ src/migrations/versions/0008_backup_run.py
+ src/shared/models/backup_run.py
+ src/shared/repositories/backup_run.py
* src/shared/config.py (BackupSettings)
* src/bot/texts.py
* src/bot/scheduler/jobs.py (новый джоб + хелперы)
* src/bot/scheduler/builder.py (условная регистрация)
* infra/Dockerfile.db-backup (инструментированный скрипт)
* infra/docker-compose.prod.yml (env + script)
+ handoff/outbox/TASK-099-report.md
```

(Полный diff — в коммитах ветки)

## Как воспроизвести / запустить

```bash
# 1. Применить миграцию
uv run alembic upgrade head

# 2. Включить фичу (для теста)
export BACKUP_HEARTBEAT_ENABLED=true
export BACKUP_MAX_AGE_HOURS=2
export ADMIN_TELEGRAM_CHAT_IDS=123456789

# 3. Перезапустить бота
make up

# 4. Тесты
uv run pytest -k "backup" -q
uv run ruff check
uv run mypy src/shared --strict
```

## Что не сделано (если применимо)

- Полная многосерверная репликация дампов и её статус в `backup_run` (backlog).
- Pending-alerts fallback на случай проблем с egress Telegram.
- Сам `pg_dump` и ротация остались в контейнере `db-backup` (как и планировалось).

## Открытые вопросы для проектировщика

Нет. Всё по спеке + proposal.

## Предложение для PROJECT_STATUS.md

2026-06-02 — **TASK-099 ЗАКРЫТ.** Backup health heartbeat: таблица `backup_run` (миграция 0008), `BackupRunRepository`, джоб `send_backup_health_heartbeat` (Cron :07, только если `BACKUP_HEARTBEAT_ENABLED`), проверка видимости БД/Redis, инструмент ация db-backup контейнера (psql INSERT/UPDATE). Условная регистрация в builder. Тексты и env в compose. PR #TBD.

## Метрики

- Основные компоненты реализованы и проверены (model + repo + job + producer side).
- Следующий шаг — полный прогон CI + merge.
