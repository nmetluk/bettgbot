---
task: TASK-048
completed: 2026-05-27
agent: claude-opus-4-7
status: done
branch: main
commit: ea16150
---

# TASK-048: ReminderDispatchLog — retention-job + индексы (отчёт)

> Отчёт восстановлен cowork-агентом ретроспективно (исполнитель пушнул `feat(scheduler)` + archive напрямую в main без отчёта в outbox — нарушение DoD пункта «Отчёт»). Содержание — синтез из коммита `ea16150` и читки кода.

## Что сделано

- **Миграция `src/migrations/versions/0004_reminder_dispatch_log_indexes.py`** добавляет 3 индекса на `reminder_dispatch_log`:
  - `ix_reminder_dispatch_log_user_id`
  - `ix_reminder_dispatch_log_event_id`
  - `ix_reminder_dispatch_log_dispatched_at`
  - `downgrade()` дропает их в обратном порядке.
- **`Settings.reminder_log_retention_days: PositiveInt = 90`** (env `REMINDER_LOG_RETENTION_DAYS`) — `src/shared/config.py`.
- **`ReminderDispatchLogRepository.delete_older_than(cutoff)`** — bulk `DELETE WHERE dispatched_at < :cutoff`, возвращает rowcount. Без `commit()` — управление транзакцией у вызывающего.
- **Job `cleanup_old_dispatch_logs`** в `src/bot/scheduler/jobs.py`: вычисляет `cutoff = now - timedelta(days=retention_days)`, открывает session, вызывает `delete_older_than`, коммитит, логирует `scheduler.cleanup_dispatch_logs.done` с `deleted_count` и `retention_days`.
- **Регистрация job** в `src/bot/scheduler/builder.py`: `CronTrigger(hour=3, minute=30)`, `misfire_grace_time=300`, после `archive_stale_events` (03:00). Получает `retention_days` через `get_settings().reminder_log_retention_days` на build-time.

## Тесты

Добавлено 5 интеграционных тестов:

- `tests/integration/test_dispatch_log_cleanup.py`:
  - `test_delete_older_than_removes_old_entries` — записи 100 и 50 дней удалены, 10-дневная осталась.
  - `test_delete_older_than_returns_zero_when_no_old_entries` — нет старых = 0.
  - `test_cleanup_job_uses_retention_from_config` — sanity что дефолт = 90.
- `tests/integration/test_migrations.py`:
  - `test_0004_creates_dispatch_log_indexes` — после `upgrade head` все 3 индекса присутствуют.
  - `test_0004_roundtrip` — `upgrade 0004 → downgrade 0003` оставляет только UNIQUE из 0002.

## Diff-сводка

```
 src/bot/scheduler/builder.py                       |  15 +-
 src/bot/scheduler/jobs.py                          |  26 +-
 src/migrations/versions/0004_reminder_dispatch_log_indexes.py |  44 +++
 src/shared/config.py                               |   2 +
 src/shared/repositories/reminder_dispatch_log.py   |  13 +-
 tests/integration/test_dispatch_log_cleanup.py     |  82 ++++++
 tests/integration/test_migrations.py               |  31 ++
 uv.lock                                            | 313 +++++++++++++++++++++
```

## Замечания от cowork-агента

1. **Конвенция archive нарушена.** Исполнитель положил `archive/TASK-048-reminder-dispatch-log-retention-indexes.md` как **flat-файл** вместо `archive/TASK-048-…/task.md` (директория). 8-е подобное нарушение подряд. Cowork исправил отдельным коммитом (`git mv` → `task.md`). Правило из DECISIONS 2026-05-26 остаётся.
2. **Direct-push в main для изменений в `src/`** — нарушение workflow («src → feature-branch + PR»). Допустимо при экстренных hotfix'ах, но TASK-048 не экстренная. На будущее — для P1-задач делать PR.
3. **uv.lock прирос 24 пакетами** (bandit, pip-audit, cyclonedx-* и др.). Это транзитивные dev-deps от TASK-040 (security scans), которые тогда не залочились. Не блокер, но стоило вынести в отдельный `chore: regenerate uv.lock`.
4. **Отчёт в outbox отсутствовал** — восстановлен этим документом.
5. **Тест `test_cleanup_job_uses_retention_from_config`** не вызывает сам job — только проверяет дефолт конфига. Тех-долг: добавить тест, который вызывает `cleanup_old_dispatch_logs` end-to-end и проверяет результат с кастомным retention.

## Команды воспроизведения

```bash
# Прогнать миграцию
make db.upgrade

# Прогнать новые тесты
uv run pytest tests/integration/test_dispatch_log_cleanup.py tests/integration/test_migrations.py::test_0004_creates_dispatch_log_indexes tests/integration/test_migrations.py::test_0004_roundtrip -v

# Запустить scheduler с новым job (cleanup сработает в 03:30 UTC)
make dev.bot
```

## Открытые вопросы

— нет (тех-долг по job-level integration test — отмечен выше как минор).
