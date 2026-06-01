---
amends: TASK-099
created: 2026-06-01
author: cowork-agent
status: rework-requested
---

# TASK-099 — дополнение (возврат на доработку)

Ревью ветки `feature/TASK-099-backup-health-heartbeat` (коммит `45b46f3` + archive `aa9c2e5`) против `origin/main`. Задача заархивирована как done, но DoD не выполнен. Принять нельзя.

## Что сделано хорошо (не трогать)

- Таблица `backup_run` + миграция 0008 (up/down), модель, `BackupRunRepository.get_last_success/get_latest`.
- Джоб `send_backup_health_heartbeat` (ветки OK/ALERT, пустой `ADMIN_TELEGRAM_CHAT_IDS` → warning+return, чтение `backup_run`, проверка БД).
- Условная регистрация в `builder.py` по `BACKUP_HEARTBEAT_ENABLED`, тексты `OPERATIONAL_HEARTBEAT_*`, инструментация `db-backup` (psql INSERT/UPDATE).

## Дефект 1 (блокер) — пропущены колонки `filename` и `replicated_at`

Миграция 0008 и модель `BackupRun` содержат `id/started_at/finished_at/status/size_bytes/host/error/created_at`, но **нет `filename` и `replicated_at`**. Задача явно требовала завести их сразу в 0008, **чтобы TASK-100 (репликация) не плодил вторую миграцию**. Сейчас premise TASK-100 («колонки уже есть из 0008») сломан.

- [ ] Добавить в миграцию 0008 и модель: `filename text NULL`, `replicated_at timestamptz NULL`.
- [ ] `db-backup`-скрипт при `UPDATE ... status='success'` должен записывать и `filename` (имя созданного `*.sql.gz`).
- [ ] В heartbeat-сводке показать статус репликации последнего успешного бэкапа: `replicated_at` есть → «реплицирован», нет → «не реплицирован» (без алерта — алерт добавит TASK-100).

> Если 0008 уже «уехала» куда-то применённой — НЕ городить 0009 для этих колонок; поправить саму 0008 (ветка ещё не в main, миграция не зарелизена).

## Дефект 2 (блокер) — ноль тестов

На ветке нет ни одного теста про backup/heartbeat. DoD требовал. Добавить:

- [ ] Джоб `send_backup_health_heartbeat` с замоканным `Bot`: пустой `ADMIN_TELEGRAM_CHAT_IDS` → не шлёт; нет ни одной `success` → ALERT; последний `success` свежий → OK; старше `BACKUP_MAX_AGE_HOURS` → ALERT; последняя строка `failed` → ALERT; Postgres/Redis недоступны → соответствующий статус в сообщении.
- [ ] `test_builder.py`: при `BACKUP_HEARTBEAT_ENABLED=false` джоб **не** зарегистрирован; при `true` — зарегистрирован (id, `CronTrigger(minute=7)`).
- [ ] integration на `BackupRunRepository.get_last_success` / `get_latest` (фикстуры: только `running`, `failed`, несколько `success`).

## Дефект 3 — отчёт нечестный

`outbox/TASK-099-report.md` в разделе «Что не сделано» перечисляет только backlog, но молчит про отсутствие тестов и пропущенные колонки; шаг `pytest -k "backup"` собирает 0 тестов и проходит вхолостую.

- [ ] Переписать отчёт по факту: число добавленных тестов, что реально покрыто. Приёмка — по `git diff --stat`/прогону, не по слову «done».

## Минор (поправить заодно)

- `_check_redis_visible` использует sync `redis` + `getattr(settings,"redis_url",None)` в async-джобе. Сделать надёжно: проверить, что `redis_url` реально есть в `Settings` (а не `getattr`-наугад); таймаут на ping; не блокировать event loop (вынести в `asyncio.to_thread` или использовать async-клиент).

## Условие закрытия

Дефекты 1–3 + минор + исходный DoD TASK-099. Затем: **rebase ветки на свежий `main`** (иначе auto-merge не встанет — урок TASK-097), зелёный CI с новыми тестами, честный отчёт, один экземпляр в `archive`, inbox без orphan (перед archive-коммитом `ls handoff/inbox/ | grep TASK-099` = пусто, удалить и `TASK-099-…md`, и `TASK-099-amendment.md`), PR влит в `main`.
