---
task: TASK-017
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/47
branch: feature/TASK-017-scheduler-reminders
commits:
  - 79ce13b chore(handoff): take TASK-017 in progress
  - 0c4cf9e feat(models): ReminderDispatchLog + миграция 0002
  - 5bf4324 feat(repositories): ReminderDispatchLogRepository
  - 40636f3 feat(services): ReminderService.find_candidates + ReminderCandidate dataclass
  - 2009a0a feat(texts): REMINDER_NOTIFICATION
  - dc348e6 feat(scheduler): AsyncIOScheduler + dispatch_reminders job
  - 2ebfeec feat(bot): scheduler в main() параллельно polling
  - 0cc5af8 test(integration): find_candidates 9 сценариев + migration 0002 table+constraint
---

# Отчёт по TASK-017: APScheduler-job рассылки напоминаний

## Сводка

Первая фоновая задача в проекте. `AsyncIOScheduler` запускается в `main()` параллельно polling и каждые 5 минут (UTC, `misfire_grace_time=60`) тикает `dispatch_reminders`. Job открывает свою сессию через `SessionLocal()`, зовёт `ReminderService.find_candidates(now, window_minutes=5)`, для каждого кандидата делает `dispatch_log.record(...)` (атомарная `pg_insert ON CONFLICT DO NOTHING RETURNING id`) и только потом `bot.send_message(...)`. Порядок именно такой: при сбое send следующий тик не повторит — момент уже прошёл, а лог уже есть.

Новая модель `ReminderDispatchLog(user_id, event_id, offset_minutes, dispatched_at)` + UNIQUE на тройку. Миграция `0002_reminder_dispatch_log` сгенерирована autogenerate, переоформлена в стиль `0001_init` (slug-revision, ruff-friendly).

`find_candidates` — один SQL: `select unnest(offsets_minutes) ... where enabled`, JOIN `User`/`Event` (`is_published AND NOT is_archived`), OUTER JOIN `Prediction` и `ReminderDispatchLog`, WHERE `EXTRACT(EPOCH FROM (predictions_close_at - :now))/60 IN [offset, offset+window)`. `User.is_blocked = FALSE` дополнительно — экономит TG-API.

`pyproject.toml`: добавлен `[[tool.mypy.overrides]] module = ["apscheduler.*"]` с `ignore_missing_imports = true` — у пакета нет `py.typed`.

`TelegramAPIError` (включая `TelegramForbiddenError` — пользователь заблокировал бота) ловим, логируем `warning` и идём к следующему кандидату. Лог не откатываем.

## Изменённые файлы

```
+ src/shared/models/reminder_dispatch_log.py            # модель
* src/shared/models/__init__.py                         # +ReminderDispatchLog
+ src/migrations/versions/0002_reminder_dispatch_log.py
+ src/shared/repositories/reminder_dispatch_log.py
* src/shared/repositories/__init__.py                   # +Repo
* src/shared/services/reminder.py                       # +ReminderCandidate + find_candidates
* src/shared/services/__init__.py                       # +ReminderCandidate
+ src/bot/scheduler/__init__.py
+ src/bot/scheduler/builder.py
+ src/bot/scheduler/jobs.py
* src/bot/main.py                                       # build_scheduler + start/shutdown
* src/bot/texts.py                                      # +REMINDER_NOTIFICATION
* pyproject.toml                                        # mypy override для apscheduler.*
+ tests/integration/services/test_reminder_service_find_candidates.py  # 9 тестов
* tests/integration/test_migrations.py                  # +reminder_dispatch_log в expected + UNIQUE
+ tests/unit/bot/scheduler/__init__.py
+ tests/unit/bot/scheduler/test_builder.py              # 1 smoke
+ tests/unit/bot/scheduler/test_dispatch_reminders.py   # 3 теста
* handoff/inbox/TASK-017-...md → archive/TASK-017-scheduler-reminders/task.md
+ handoff/outbox/TASK-017-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    117 files already formatted
mypy src/shared src/bot          Success: no issues found in 60 source files
pytest -m "not integration"      153 passed in 1.53s
pytest tests/integration         85 passed in 9.23s

CI PR #47 — все четыре job'а зелёные:
  Lint (ruff)                              9s
  Typecheck (mypy)                         16s
  Tests (pytest, unit)                     18s
  Integration (alembic on real postgres)   49s
```

Pre-task cleanup PR [#46](https://github.com/nmetluk/bettgbot/pull/46) свернул правки cowork (`state/PROJECT_STATUS.md`, `state/DECISIONS.md`, `sessions/2026-05-24-02-task-016-review/`, новая задача TASK-017).

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
make up && make migrate

uv run pytest -m "not integration" -v
uv run pytest tests/integration -m integration -v

# Ручная проверка scheduler'а (опц.):
# 1) В psql: создать user(tg_user_id=<свой>), reminder_setting(enabled=true, offsets_minutes={5}),
#    event(is_published=true, predictions_close_at = now() + interval '7 minutes', и outcomes).
# 2) uv run python -m src.bot.main
# 3) В логах: scheduler.started, через ~5 мин scheduler.reminder.sent.
# 4) В TG — сообщение «🔔 Напоминание! ...».
# 5) Запись в reminder_dispatch_log появилась.
```

## Что не сделано / вынесено

1. **Cleanup старых `reminder_dispatch_log`** — таблица растёт линейно с активностью. В `BACKLOG` (TTL-job или партиции по `dispatched_at`).
2. **Index `ix_reminder_dispatch_log_dispatched_at`** для будущего cleanup — не делал (MVP, никаких запросов по `dispatched_at` пока нет). В `BACKLOG`.
3. **Multi-instance HA** — на MVP один инстанс бота, никаких Redis-locks. `on_conflict_do_nothing` в `record` уже защищает от гонки между двумя scheduler'ами, если когда-нибудь.
4. **Ручной dry-run в Telegram** не делал — для этого нужен реальный TG-бот, тестовый аккаунт и событие в нужное время. CI + integration тесты на реальном Postgres покрывают всю SQL-логику.

## Открытые вопросы для проектировщика

1. **`User.is_blocked = FALSE` фильтр в `find_candidates`** — добавил, хотя в task.md он не указан явно. Логика: смысла слать заблокированным админом юзерам нет, а TG-API всё равно вернёт ошибку. Если хотим слать всем (например, для аудита/тестов) — уберём. Добавил отдельный integration-тест `test_find_candidates_blocked_user_excluded`.
2. **mypy-override для `apscheduler.*`** в `pyproject.toml` — пакет не имеет `py.typed`. Альтернатива — `# type: ignore[import-untyped]` на каждом import'е, что шумнее. Окей?
3. **`session_maker` ↔ `SessionLocal`** — task.md просит экспортировать `session_maker`. Уже есть `SessionLocal: async_sessionmaker[AsyncSession]` в `src/shared/db.py`. Использую его напрямую — не переименовываю, чтобы не трогать чужие импорты. Если хотим переименовать ради единообразия с task.md — отдельной мелкой задачей.
4. **`REMINDER_NOTIFICATION` форматирует `predictions_close_at` через `strftime("%d.%m %H:%M")` в UTC** — без таймзоны пользователя. Это MVP; локализация по таймзоне — отдельная задача, если потребуется.
5. **`InaccessibleMessage` / `TelegramForbiddenError`** — оба наследуются от `TelegramAPIError`, поэтому ловятся одним `except`. Если нужна отдельная метрика «бот заблокирован vs другой fail» — `isinstance` ветвление в обработчике; пока — общий warning.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-017: первая фоновая задача в проекте. `AsyncIOScheduler` параллельно polling, job `dispatch_reminders` каждые 5 минут (UTC, misfire_grace_time=60). Новая модель `ReminderDispatchLog` + миграция `0002` (UNIQUE на user/event/offset для дедупликации). `ReminderService.find_candidates(now, window_minutes)` — один SQL с `unnest(offsets_minutes)` + JOIN'ами, исключает по prediction, dispatch_log, blocked, archived, unpublished. Идемпотентность: `record` ДО `send_message`. 13 новых тестов (9 integration find_candidates + 3 unit dispatch_reminders + 1 smoke builder; +1 migration). `pyproject.toml`: mypy-override для apscheduler. PR [#47](https://github.com/nmetluk/bettgbot/pull/47) → squash `2c57942`. Pre-task cleanup [#46](https://github.com/nmetluk/bettgbot/pull/46).
```

## Метрики

- Файлов добавлено: 10 (model + migration + repo + 3 scheduler + 4 теста + report)
- Файлов изменено: 8 (models/__init__, repos/__init__, services/__init__, reminder.py, main.py, texts.py, pyproject.toml, test_migrations.py)
- Тестов добавлено: 13 unit/integration + 1 migration = всего 153 unit + 85 integration (было 149 + 75)
- Время на выполнение: ~60 мин (включая cleanup PR, autogenerate миграции, борьбу с apscheduler stubs)
