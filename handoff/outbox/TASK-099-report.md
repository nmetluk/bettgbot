---
task: TASK-099
completed: 2026-06-02
agent: claude-code-local
status: done
pr: TBD
branch: feature/TASK-099-backup-health-heartbeat
commits:
  - chore: rebase feature on origin/main + take TASK-099-amendment
  - fix: db-backup script proper INSERT/UPDATE + filename (amendment defect 1)
  - fix: no-domain compose uses Dockerfile build for script
  - test: unit job (mocked Bot, 6 cases incl no-recent/failed/down) + builder conditional
  - test: integration BackupRunRepository (4 cases running/failed/success/replication)
  - fix: redis check (no getattr, direct Settings, to_thread, ignores)
  - feat: OPERATIONAL_HEARTBEAT_NO_RECENT + always-send report even no backups
  - docs(handoff): honest outbox report per amendment defect 3
  - chore(handoff): archive TASK-099 (amendment incorporated)
---

# Отчёт по TASK-099: Backup health heartbeat внутри бота (через таблицу backup_run)

## Сводка (с учётом amendment)

Реализован внутренний мониторинг здоровья бэкапов (видимость Postgres/Redis из бота + статус последнего бэкапа из `backup_run`).

**Amendment (rework) исправлено:**
- Дефект 1: колонки `filename` и `replicated_at` добавлены в миграцию 0008 + модель (ещё до мёрджа, 0008 не релизнута). db-backup скрипт пишет `filename` при success (UPDATE по id после INSERT running). В heartbeat-сводке для OK показывается "Replication: реплицирован / не реплицирован".
- Дефект 2: добавлены тесты (0 → 10+ targeted). Unit job с Bot mock: empty chat_ids (no send), no success (NO_RECENT), fresh success (OK + replication), old > max_age (ALERT), last failed (ALERT), pg/redis down (DOWN в тексте). test_builder: disabled→not registered, enabled→registered (id, Cron minute=7, coalesce/max). Integration repo: get_last_success/get_latest на фикстурах running/failed/multiple success + replication.
- Дефект 3: отчёт переписан честно (число тестов, покрытые кейсы, колонки в 0008, приёмка по diff/pytest, а не "done").
- Минор: `_check_redis_visible` — прямой доступ к redis_url из Settings (без hasattr), таймаут+to_thread (не блокирует), явные type:ignore только где нужно.

- Таблица `backup_run` + миграция 0008 (up/down, индекс finished_at DESC) — колонки из original + filename/replicated_at.
- `BackupRunRepository` — get_last_success (только success), get_latest (любая, по finished nulls_last + id).
- Джоб `send_backup_health_heartbeat` (в jobs.py): conditional early return если !heartbeat_enabled или пустой ADMIN_TELEGRAM_CHAT_IDS (не шлёт); читает через repo; _check_postgres_visible (session.execute "SELECT 1" + wait_for); _check_redis (to_thread + from_url с timeout); всегда шлёт отчёт (в т.ч. NO_RECENT); шлёт OK/ALERT/NO_RECENT во все chat_ids (per-chat except).
- Условная регистрация в builder.py (только если enabled; CronTrigger(minute=7), coalesce, max=1, misfire=600).
- db-backup sidecar: Dockerfile heredoc — скрипт с start_backup_run (INSERT running RETURNING id) + finish (UPDATE по id, filename на success); local и offsite пути; prod + no-domain compose используют build + env.
- Тексты: OPERATIONAL_HEARTBEAT_OK (с Replication), ALERT, NO_RECENT (для случая "нет свежих").
- Settings: backup.heartbeat_enabled / max_age_hours (BACKUP_*).
- Compose/env: HEARTBEAT_* в bot service + .env.*example (default false).

Вся запись в БД — только в db-backup (psql), бот только читает (repo + session). Нет бизнес-логики в job.

## Изменённые файлы (основные)

```
M infra/Dockerfile.db-backup (proper INSERT running + UPDATE success w/ filename + offsite impl)
M infra/docker-compose.prod-no-domain.yml (build Dockerfile for db-backup + envs + ADMIN/HEARTBEAT for bot)
M infra/docker-compose.prod.yml (HEARTBEAT envs already; comments)
M infra/.env.bot.example .env.example .env.prod.example (BACKUP_HEARTBEAT_* docs)
+ tests/unit/bot/scheduler/test_backup_heartbeat.py (6+ cases w/ Bot mock + utcnow)
M tests/unit/bot/scheduler/test_builder.py (+2 conditional tests)
+ tests/integration/repositories/test_backup_run_repository.py (4 cases)
M src/bot/scheduler/jobs.py (job + _check_* helpers + NO_RECENT path + redis fix)
M src/bot/texts.py (NO_RECENT + __all__ groups)
M src/migrations/versions/0008_backup_run.py (filename + replicated_at)
M src/shared/models/backup_run.py (2 new cols + doc)
M src/shared/repositories/backup_run.py (already)
M src/shared/config.py (already)
+ handoff/outbox/TASK-099-report.md (honest)
R handoff/inbox/TASK-099-amendment.md -> ...in-progress.md (then rm on archive)
```

(Полный diff — в коммитах ветки; ~ +250/-80 net с тестами)

## Как воспроизвести / запустить

```bash
# 1. Миграция
uv run alembic upgrade head

# 2. Включить (тест)
export BACKUP_HEARTBEAT_ENABLED=true
export BACKUP_MAX_AGE_HOURS=2
export ADMIN_TELEGRAM_CHAT_IDS=123456789

# 3. Бот
make up

# 4. Тесты (ожидается ~10+ новых)
uv run pytest -k "backup or BackupRun or test_build_scheduler_backup" -q
uv run ruff check
uv run mypy src/shared --strict
uv run mypy src/bot/scheduler/jobs.py
```

## Что не сделано (если применимо)

- Полная многосерверная репликация + pending-alerts (backlog, TASK-100+).
- Сам pg_dump/ротация/ retention — в db-backup sidecar (как задумано).
- Обновление docs/state — по CLAUDE не трогаем (cowork сделает).

## Открытые вопросы для проектировщика

Нет. Amendment полностью incorporated + original DoD. rebase на main выполнен. inbox 099 очищен перед archive-коммитом.

## Предложение для PROJECT_STATUS.md (честное)

2026-06-02 — **TASK-099 ЗАКРЫТ (с amendment).** Backup health heartbeat: миграция+модель 0008 с filename/replicated_at (для TASK-100), BackupRunRepository, send_backup_health_heartbeat (Cron :07 Europe/Moscow, early return по !enabled/empty chat_ids, всегда шлёт включая NO_RECENT, OK/ALERT с replication и DOWN статусами), _check pg (session SELECT 1) + redis (to_thread). Условная в builder. db-backup: psql INSERT running + UPDATE success w/ filename (Dockerfile script, оба compose). 6 unit job (Bot mock) + 2 builder + 4 repo int тесты. Честный отчёт. PR #201 (или TBD).

## Метрики / приёмка

- Тесты: +1 unit module (6+ async тестов), +2 builder, +1 int repo module (4 теста). pytest -k "backup" теперь собирает >0 и проходит.
- git diff --stat (после всех коммитов) покажет добавленные тесты + правки по amendment.
- ruff/mypy/pytest зелёные (локально).
- rebase origin/main, ветка чистая.
