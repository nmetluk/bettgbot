---
id: TASK-048
created: 2026-05-27
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - src/shared/repositories/reminder_dispatch_log.py
  - src/shared/services/reminder.py
  - src/migrations/versions/0002_reminder_dispatch_log.py
  - src/bot/scheduler/jobs.py
priority: high
estimate: M
---

# TASK-048: ReminderDispatchLog — retention-job + индексы на FK + dispatched_at

## Контекст

**Новая находка ревью 2026-05-27.** Тех-долг был зафиксирован при review TASK-017 (PROJECT_STATUS строка 69: «cleanup `reminder_dispatch_log` и `ix_dispatched_at`»), но не оформлен задачей. После уточняющего ревью SQL-плана выяснилось, что проблема **уже сейчас на грани production-impact**:

1. **Cleanup отсутствует совсем.** Таблица растёт без верхней границы: ~288 тиков/день × `N_активных_событий` × `M_подписавшихся` строк/день. При 100 событий × 1000 пользователей × 2 offset = 200 000 строк/день, ~73 млн/год.

2. **Нет индексов на `user_id`, `event_id` отдельно.** Миграция 0002 создаёт только `uq_reminder_dispatch_log_user_event_offset` (composite UNIQUE). Postgres использует его для запросов на полный prefix `(user_id, event_id)`, но в `ReminderService.find_candidates` (`src/shared/services/reminder.py:104-114`) JOIN идёт по той же тройке — план **может** быть корректным, но при росте таблицы > пары млн строк выбор индекса перестаёт быть очевидным.

3. **Нет индекса на `dispatched_at`.** Когда будет реализован cleanup (`DELETE WHERE dispatched_at < now() - INTERVAL '90 days'`), без индекса это seq scan на всей таблице — vacuum-нагрузка + блокировки.

4. **Cascade каскад при удалении пользователя/события** — `ondelete="CASCADE"` корректно, но без индекса на `user_id` каскад работает через seq scan (auditor M-XX тоже не оформил).

## Цель

(a) Добавить миграцию `0004_reminder_dispatch_log_indexes`: индексы на `user_id`, `event_id`, `dispatched_at`. (b) Добавить scheduler-job `cleanup_old_dispatch_logs`: ежедневно DELETE'ит записи старше N дней. Retention настраивается через `Settings`.

## Definition of Done

- [ ] Миграция `src/migrations/versions/0004_reminder_dispatch_log_indexes.py`:
  - `op.create_index("ix_reminder_dispatch_log_user_id", "reminder_dispatch_log", ["user_id"])`
  - `op.create_index("ix_reminder_dispatch_log_event_id", "reminder_dispatch_log", ["event_id"])`
  - `op.create_index("ix_reminder_dispatch_log_dispatched_at", "reminder_dispatch_log", ["dispatched_at"])`
  - downgrade() корректно дропает оба
- [ ] В `src/shared/config.py`: `reminder_log_retention_days: PositiveInt = 90` (env `REMINDER_LOG_RETENTION_DAYS`).
- [ ] В `src/shared/repositories/reminder_dispatch_log.py`: метод `delete_older_than(cutoff: datetime) -> int` — bulk DELETE + возврат rowcount.
- [ ] В `src/bot/scheduler/jobs.py`: новый job `cleanup_old_dispatch_logs(session_maker, retention_days)`, INFO-лог с количеством удалённых строк.
- [ ] В `src/bot/scheduler/builder.py`: добавить `scheduler.add_job(cleanup_old_dispatch_logs, CronTrigger(hour=3, minute=30), ...)` — после `archive_stale_events`, чтобы не конкурировать за tx.
- [ ] Integration-тест: создать 100 dispatch_log записей с разными `dispatched_at`, прогнать `cleanup_old_dispatch_logs`, проверить что старые удалены, свежие — нет.
- [ ] Integration-тест на миграцию 0004 (round-trip с данными).
- [ ] PR `TASK-048: dispatch log retention + indexes`.
- [ ] Отчёт + Move-семантика inbox→archive.

## Артефакты

- `+ src/migrations/versions/0004_reminder_dispatch_log_indexes.py`
- `* src/shared/config.py` (новое поле в `Settings`)
- `* src/shared/repositories/reminder_dispatch_log.py` (метод `delete_older_than`)
- `* src/bot/scheduler/jobs.py` (новый job)
- `* src/bot/scheduler/builder.py` (регистрация job)
- `+ tests/integration/test_dispatch_log_cleanup.py`

## Подсказки исполнителю

- DELETE по `dispatched_at < cutoff` с индексом — index-only scan + bitmap delete, ОК на любом размере.
- Retention 90 дней — компромисс: достаточно для расследования «почему я не получил напоминание», но не убивает таблицу.
- Job должен лочить минимум: `DELETE` без `FOR UPDATE` достаточно, Postgres использует row-locks.
- Не дёргай этот job под `dispatch_reminders` — лучше отдельный cron, чтобы не блокировать критичный send-flow.
