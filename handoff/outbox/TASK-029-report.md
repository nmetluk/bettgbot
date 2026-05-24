# TASK-029: pg_dump cron-бэкап БД в Docker volume — отчёт

## Что сделано

- **db-backup сервис** в `infra/docker-compose.prod.yml`:
  - Образ `postgres:16-alpine`
  - Sleep-loop до 02:30 UTC, затем бэкап каждые 24 часа
  - `pg_dump --no-owner --clean --if-exists | gzip`
  - Retention 14 дней (`find -mtime +14 -delete`)
  - Логирование ошибок с префиксом `[backup-error]`
- **bb-db-backups volume** — named volume для дампов
- **Makefile цели**:
  - `prod.backup.now` — однократный бэкап
  - `prod.backup.ls` — список дампов
  - `prod.backup.restore` — восстановление с подтверждением

## Коммиты

- `68c6eae` feat(infra): TASK-029 pg_dump cron-бэкап БД в Docker volume

## Smoke-тест (локально)

```bash
# Запуск prod-stack (без nginx — не требуется для теста)
make prod.up
# Ожидание запуска db + db-backup
make prod.backup.now
# Проверка:
make prod.backup.ls
# Должен показать файл вида bettgbot-YYYY-MM-DDTHH-MM-SSZ.sql.gz
```

## Восстановление

```bash
make prod.backup.restore FILE=bettgbot-2026-05-25T02-30-00Z.sql.gz
# Требует ввода "RESTORE"
```

## PR

https://github.com/nmetluk/bettgbot/pull/81
