---
id: TASK-101
created: 2026-06-02
author: cowork-agent
parallel-safe: false
blockedBy: [TASK-100]
related:
  - infra/Dockerfile.db-backup
  - handoff/archive/TASK-029-pg-dump-backup
  - handoff/archive/TASK-099-backup-health-heartbeat
priority: normal
estimate: S
---

# TASK-101: Ежечасный бэкап БД (вместо суточного) + использовать BACKUP_RETENTION_DAYS

## Контекст

Сейчас контейнер `db-backup` (TASK-029) делает дамп **раз в сутки**: в `infra/Dockerfile.db-backup` обе петли (`run_local_backup_loop`, offsite-петля) гейтятся по времени (`target_time="0230"`, при срабатывании `sleep 86400`, иначе `sleep 300`). Владелец хочет **ежечасные** бэкапы.

Дополнительно: retention захардкожен `find /backups -name "bettgbot-*.sql.gz" -mtime +14 -delete`, хотя env `BACKUP_RETENTION_DAYS` уже объявлен в compose (`infra/docker-compose.prod-no-domain.yml`, default 30) и **не используется** — рассинхрон, поправить заодно.

Ежечасный бэкап делает осмысленным порог `BACKUP_MAX_AGE_HOURS=2` из heartbeat (TASK-099): теперь алерт «бэкап старше 2ч» реально сигналит о проблеме. Каждый дамп пишет строку в `backup_run` (TASK-099), репликация (TASK-100) подхватывает каждый новый файл.

`blockedBy: TASK-100` — обе задачи трогают `Dockerfile.db-backup`/prod-compose; делаем последовательно, чтобы не ловить merge-конфликты.

## Цель

`db-backup` создаёт дамп раз в час (интервал конфигурируемый), retention управляется через `BACKUP_RETENTION_DAYS`.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-101-report.md`.

- [ ] В `infra/Dockerfile.db-backup` обе петли (`run_local_backup_loop` и offsite): убрать суточный time-gate (`target_time="0230"` / `current_time -ge`), сделать ежечасный цикл — дамп → `sleep "$BACKUP_INTERVAL_SECONDS"`; на ошибке pg_dump — `sleep 300` (короткий ретрай) и продолжить. Поведение записи в `backup_run` (`start_backup_run`/`finish_backup_run` с filename) **сохранить как есть** (TASK-099).
- [ ] Новый env `BACKUP_INTERVAL_SECONDS` (default `3600`). Прочитать в скрипте с дефолтом: `BACKUP_INTERVAL_SECONDS=${BACKUP_INTERVAL_SECONDS:-3600}`.
- [ ] Retention: заменить хардкод `-mtime +14` на использование `BACKUP_RETENTION_DAYS` (default согласовать единым — предлагаю `7` для ежечасной схемы; обоснование ниже). Применить в обеих петлях.
- [ ] env-проводка: `BACKUP_INTERVAL_SECONDS` (+ при необходимости унифицировать `BACKUP_RETENTION_DAYS`) в сервис `db-backup` в `infra/docker-compose.prod.yml` и `infra/docker-compose.prod-no-domain.yml`, плюс `infra/.env.*example` с комментарием.
- [ ] Проверка: `docker compose -f infra/docker-compose.prod.yml up db db-backup` (или no-domain) — за >1ч (или с временно `BACKUP_INTERVAL_SECONDS=60` для теста) появляются дампы каждый интервал, в `backup_run` по строке на запуск, старые подчищаются по retention. Зафиксировать в отчёте, как проверял.
- [ ] `ruff format --check src tests` и `ruff check src tests` зелёные (даже если правки только в infra — прогнать, это повторяющийся блокер CI; код в src не трогается).
- [ ] PR `TASK-101: hourly backup`; отчёт в outbox; move inbox→archive; ветка отребейзена на свежий `main` перед PR.

## Решение по retention (обосновать в отчёте, если меняешь)

Ежечасно × `RETENTION_DAYS`: при 14 днях это ~336 gzip-дампов, при 7 — ~168. Предлагаю **default 7 дней** для ежечасной схемы (recovery-окно неделя, разумный объём). Если владелец захочет глубже — поднимет env. В отчёте указать итоговый default и прикинуть объём (размер одного дампа × число файлов).

## Артефакты

```
* infra/Dockerfile.db-backup                 # ежечасный цикл + BACKUP_INTERVAL_SECONDS + BACKUP_RETENTION_DAYS
* infra/docker-compose.prod.yml              # env db-backup
* infra/docker-compose.prod-no-domain.yml    # env db-backup
* infra/.env.example, .env.prod.example      # BACKUP_INTERVAL_SECONDS (+ retention)
```

## Ссылки

- Текущий бэкап: [`infra/Dockerfile.db-backup`](../../infra/Dockerfile.db-backup) (`run_local_backup_loop`), TASK-029
- Heartbeat-порог: TASK-099 (`BACKUP_MAX_AGE_HOURS`, default 2)
- Репликация каждого дампа: TASK-100

## Границы

- Только инфра (bash-петля + compose + env). В `src/` ничего не меняется, миграций нет.
- Логику записи `backup_run` и offsite (age/rclone) **не переделывать** — только частота + retention-env.
- `docs/`/`state/` не трогать — обновит cowork.
