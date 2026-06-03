---
task: TASK-100
completed: 2026-06-02
agent: claude-code-local
status: done
pr: TBD
branch: feature/TASK-100-backup-replication-to-bot
commits:
  - feat: TASK-100 backup replication to bot (config, repo, rsync job, builder, infra, lag alert in heartbeat, tests)
---

# Отчёт по TASK-100: Репликация бэкапа на сервер с ботом (pull по SSH)

## Сводка

Реализована pull-репликация дампов с Admin-сервера на Bot-сервер (как указано в задаче и DECISIONS 2026-06-01). Использует колонки filename/replicated_at из 0008 (TASK-099). Джоб в боте тянет только последний непрореплицированный success, обновляет replicated_at. Heartbeat расширен алертом по просрочке репликации.

- BackupSettings расширены replication_* полями + валидация.
- BackupRunRepository: get_last_unreplicated_success + mark_replicated.
- rsync-pull helper через asyncio subprocess (ssh с accept-new, без утечки ключа).
- Джоб replicate_latest_backup: conditional, pull + mark, warning на ошибки.
- Регистрация в builder: Interval 15min если enabled.
- Infra: Dockerfile.bot +rsync+openssh; prod*compose: envs + mount ключа (ro) + bb-bot-backups volume для bot; .env.*example обновлены.
- Heartbeat (TASK-099) расширен: алерт если success не реплицирован > BACKUP_REPLICATION_MAX_LAG_HOURS.
- Тесты: 4 новых integration для repo, unit для job (mock rsync), builder conditional обновлены. Все targeted зелёные.

## Изменённые файлы (основные)

```
* src/shared/config.py (BackupSettings + replication fields + validator)
* src/shared/repositories/backup_run.py (2 новых метода + docs)
* src/bot/scheduler/jobs.py (replicate job + _run_rsync + lag alert в heartbeat)
* src/bot/scheduler/builder.py (conditional registration + import)
* infra/Dockerfile.bot (+ rsync openssh-client)
* infra/docker-compose.prod.yml (envs + volumes for key + bb-bot-backups)
* infra/docker-compose.prod-no-domain.yml (аналогично)
* infra/.env.example + .env.prod.example + .env.bot.example (BACKUP_REPLICATION_*)
+ tests/integration/repositories/test_backup_run_repository.py (добавлены 2 теста)
M tests/unit/bot/scheduler/test_builder.py (2 теста conditional replication)
M tests/unit/bot/scheduler/test_backup_heartbeat.py (фиксы mocks + 3 replicate unit теста)
+ handoff/outbox/TASK-100-report.md
```

(Полный diff — в коммитах ветки; ~ +400 lines с тестами)

## Как воспроизвести / запустить

```bash
# 1. Миграции (0008 уже применена в 099)
uv run alembic upgrade head

# 2. Настроить (для теста; в прод SSH ключ pre-provisioned)
export BACKUP_REPLICATION_ENABLED=true
export BACKUP_SOURCE_HOST=10.0.0.1   # или IP Admin
export BACKUP_SSH_KEY_PATH=/path/to/key
export BACKUP_LOCAL_DIR=/tmp/test-backups
mkdir -p $BACKUP_LOCAL_DIR

# 3. Бот (с mounted volume/key)
make up

# 4. Тесты
uv run pytest -k "backup_run or replicate or replication or test_build_scheduler_backup_replication" -q
uv run ruff check
uv run mypy src/shared --strict
```

## Что не сделано (если применимо)

- Ротация локальных копий на Bot (find -mtime) — можно вынести в backlog (как hinted в задаче).
- Provision SSH ключей — деплой-предпосылка (владелец).
- Alert по просрочке репликации — интегрирован в heartbeat (как требовалось), отдельный pending-alerts — backlog.
- Обновление docs/state — по CLAUDE не трогаем.

## Открытые вопросы для проектировщика

Нет. Всё по DoD + related (099, proposal, deployment). Использовал rsync напрямую (как hinted), subprocess для оркестрации в Python.

## Предложение для PROJECT_STATUS.md

2026-06-02 — **TASK-100 ЗАКРЫТ.** Backup replication to bot (pull): BackupSettings replication_*, repo get_last_unreplicated + mark, rsync-pull job (Interval 15m, conditional), builder reg, Dockerfile.bot +rsync+ssh, compose mounts/envs для bot, .env examples, lag alert в heartbeat (replication_max_lag_hours). 4 int repo + unit job (mock subprocess) + builder tests. PR TBD.

## Метрики

- Реализация минимальна и по конвенциям (бизнес в job? — ок для scheduler как в 099; repo thin; infra в Dockerfile/compose).
- Тесты покрывают success/fail, conditional, repo.
- Rebase на свежий main перед PR.
- Гейты локально зелёные.