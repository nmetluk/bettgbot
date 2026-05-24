---
id: TASK-018
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md (раздел «Фоновые задачи → Архивация (страховка)»)
  - docs/03-data-model.md
  - src/shared/services/event.py
  - src/bot/scheduler/builder.py
  - src/bot/scheduler/jobs.py
priority: high
estimate: M
---

# TASK-018: APScheduler-job автоматической архивации стейлевых событий

## Контекст

**Вторая и последняя фоновая задача в проекте**, закрывающая **Этап 2 (Telegram-бот)**. Намного проще TASK-017 — scheduler infrastructure уже готова (`src/bot/scheduler/`), нужно только добавить новый job + сервисный метод.

Спецификация — [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md), раздел «Фоновые задачи → Архивация (страховка)»:

> APScheduler-job ежедневно: помечает `is_archived = true` события, у которых `starts_at < now - 7 дней` и `result_outcome_id IS NULL` (то есть админ забыл зафиксировать). Эти события не дают пользователю прогнозировать, но видны в архиве **без** отметки «сбылся/нет» (NULL).

Это **страховка** от ситуации, когда событие прошло, но админ не успел зафиксировать итог через UI админки. Без архивации такое событие висело бы в каталоге, и пользователь видел бы его как «активное» (хоть `predictions_close_at` уже прошёл — кнопка прогноза не покажется, но карточка останется в списке).

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) раздел «Фоновые задачи».
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — поля `Event.is_archived`, `archived_at`, `result_outcome_id`, `starts_at`.
- [`src/shared/services/event.py`](../../src/shared/services/event.py) — текущий `EventService`. Уже есть `set_result(event_id, outcome_id, archived_at)`, который архивирует событие при фиксации итога — это «нормальный» путь. Сейчас добавим «страховочный» путь без `outcome_id`.
- [`src/shared/repositories/event.py`](../../src/shared/repositories/event.py) — текущий `EventRepository`.
- [`src/bot/scheduler/builder.py`](../../src/bot/scheduler/builder.py) + [`src/bot/scheduler/jobs.py`](../../src/bot/scheduler/jobs.py) — текущая scheduler infra. Добавим второй job.

## Перед стартом — pre-task cleanup PR

В origin/main `980c591` — last commit (archive TASK-017). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-017, новый шаг TASK-018.
- `state/DECISIONS.md` — 4 новых строки (`is_blocked` filter, mypy-override, `SessionLocal` naming, идемпотентность scheduler-job).
- `state/BACKLOG.md` — 2 новых пункта тех-долга (cleanup `reminder_dispatch_log`, `ix_dispatched_at`).
- Новая сессия `sessions/2026-05-24-03-task-017-review/`.
- `handoff/inbox/TASK-018-scheduler-archive.md` — эта задача.

Branch: `chore/post-TASK-017-cowork-cleanup`, PR `chore(handoff): post-TASK-017 review by cowork`. После merge — `feature/TASK-018-scheduler-archive`.

## Цель

Бот, запущенный через `python -m src.bot.main`, ежедневно в 03:00 UTC автоматически помечает стейлевые события как архивные. Прогнозы пользователей по этим событиям остаются с `is_correct = NULL` (без отметки «сбылся/нет»). Покрыто integration-тестами на сервисный метод + unit-тестами на job + регистрацией job'а в scheduler.

## Definition of Done

### Step 1 — `EventService.archive_stale_events`

- [ ] **В `src/shared/services/event.py`** добавить:
  ```python
  from datetime import UTC, datetime, timedelta


  class EventService:
      # ... existing methods

      async def archive_stale_events(
          self, *, now: datetime | None = None, threshold_days: int = 7
      ) -> int:
          """Помечает `is_archived=True` события без итога, у которых
          `starts_at < now - threshold_days`.

          Returns: количество архивированных событий.

          Это страховка: нормальный путь архивации — через `set_result` при
          фиксации итога админом. Если админ забыл — этот job через
          `threshold_days` дней автоматически архивирует, чтобы событие не
          висело в каталоге. Прогнозы по таким событиям остаются с
          `is_correct = NULL`.
          """
          now = now or datetime.now(tz=UTC)
          cutoff = now - timedelta(days=threshold_days)
          archived_count = await self._events.archive_stale(cutoff=cutoff)
          if archived_count > 0:
              await self._session.commit()
          return archived_count
  ```
  - Принимает `now` как параметр (для детерминированных тестов с `freezegun`-альтернативой через явную передачу), defaults to `datetime.now(tz=UTC)`.
  - `threshold_days` — настраиваемый, defaults 7 по спецификации.
  - **НЕ пишет audit-лог** — это автоматическое действие без админа. Если когда-нибудь захочется отдельная audit-запись с `admin_id=NULL` — отдельная задача, потребует расширения `AuditLog` модели (поле `actor` ENUM или nullable `admin_id`).

### Step 2 — `EventRepository.archive_stale`

- [ ] **В `src/shared/repositories/event.py`** добавить:
  ```python
  from datetime import datetime


  class EventRepository:
      # ... existing methods

      async def archive_stale(self, *, cutoff: datetime) -> int:
          """Bulk-update: `is_archived=true, archived_at=now()` для всех событий
          с `starts_at < cutoff AND result_outcome_id IS NULL AND is_archived = false`.

          Returns: количество затронутых строк.
          """
          stmt = (
              update(Event)
              .where(
                  Event.starts_at < cutoff,
                  Event.result_outcome_id.is_(None),
                  Event.is_archived.is_(False),
              )
              .values(is_archived=True, archived_at=func.now())
          )
          result = await self._session.execute(stmt)
          return int(result.rowcount or 0)  # type: ignore[attr-defined]
  ```
  - Импорт `update`, `func` из sqlalchemy.
  - `# type: ignore[attr-defined]` на `rowcount` — стандартный паттерн в проекте (см. `PredictionRepository.mark_correctness`).

### Step 3 — Job в `src/bot/scheduler/jobs.py`

- [ ] **Расширить `src/bot/scheduler/jobs.py`** (рядом с `dispatch_reminders`):
  ```python
  async def archive_stale_events(*, session_maker: async_sessionmaker) -> None:
      """Ежедневный job: архивирует события старше 7 дней без итога.

      Без TG-side-effects — только update в БД. Логирует количество.
      """
      async with session_maker() as session:
          service = EventService(session)
          count = await service.archive_stale_events()
          logger.info("scheduler.archive_stale.done", archived_count=count)
  ```
  - Не принимает `bot` (в отличие от `dispatch_reminders`) — job без TG-side-effects.
  - Импорт `EventService` из `src.shared.services`.
  - `__all__` обновить: добавить `archive_stale_events`.

### Step 4 — Регистрация в `src/bot/scheduler/builder.py`

- [ ] **Обновить `build_scheduler`**:
  ```python
  from apscheduler.triggers.cron import CronTrigger
  # ... existing imports

  from .jobs import archive_stale_events, dispatch_reminders


  def build_scheduler(
      *, bot: Bot, session_maker: async_sessionmaker
  ) -> AsyncIOScheduler:
      scheduler = AsyncIOScheduler(timezone="UTC")

      scheduler.add_job(
          dispatch_reminders,
          trigger=IntervalTrigger(minutes=5),
          kwargs={"bot": bot, "session_maker": session_maker},
          id="dispatch_reminders",
          replace_existing=True,
          misfire_grace_time=60,
      )

      scheduler.add_job(
          archive_stale_events,
          trigger=CronTrigger(hour=3, minute=0),  # 03:00 UTC ежедневно
          kwargs={"session_maker": session_maker},
          id="archive_stale_events",
          replace_existing=True,
          misfire_grace_time=300,  # 5 минут — для cron'а можно щедрее
      )

      return scheduler
  ```
  - `CronTrigger(hour=3, minute=0)` — ежедневно в 03:00 UTC. Тихое время для всех TZ.
  - `misfire_grace_time=300` — 5 минут, потому что cron-job менее чувствителен к точному времени.

### Step 5 — Расширить `tests/unit/bot/scheduler/test_builder.py`

- [ ] Добавить тест:
  ```python
  def test_build_scheduler_registers_archive_stale_events_job() -> None:
      """В scheduler зарегистрирован job archive_stale_events с CronTrigger."""
      scheduler = build_scheduler(bot=MagicMock(spec=Bot), session_maker=MagicMock())
      jobs = {j.id: j for j in scheduler.get_jobs()}

      assert "archive_stale_events" in jobs
      job = jobs["archive_stale_events"]
      trigger = job.trigger
      # CronTrigger.fields — список полей; проверяем hour=3, minute=0
      hour_field = next(f for f in trigger.fields if f.name == "hour")
      minute_field = next(f for f in trigger.fields if f.name == "minute")
      assert str(hour_field) == "3"
      assert str(minute_field) == "0"
  ```
  - Если API CronTrigger.fields отличается в версии APScheduler — адаптируй проверку.
  - Существующий `test_build_scheduler_registers_dispatch_reminders_job` остаётся как есть.

### Step 6 — `tests/unit/bot/scheduler/test_archive_stale_events.py` (новый)

- [ ] 2 unit-теста:
  - `test_archive_stale_events_calls_service_with_session_and_logs_count`:
    - mock `session_maker` возвращает context-manager c mock session.
    - mock `EventService.archive_stale_events` → 3.
    - Запускаем job → проверяем, что `archive_stale_events` зван и логирование вызвано.
  - `test_archive_stale_events_handles_zero_archived`:
    - mock → 0.
    - Проверяем, что лог всё равно вызван (метрика «job отработал, но никого не нашёл»).

### Step 7 — `tests/integration/services/test_event_service_archive_stale.py` (новый)

- [ ] 5 integration-тестов на реальном Postgres:
  - `test_archive_stale_events_archives_old_unresolved_event`:
    - Создаём event с `starts_at = now - 10 days`, `result_outcome_id=None`, `is_archived=False`.
    - `service.archive_stale_events()` → возвращает 1.
    - Перечитываем event → `is_archived=True`, `archived_at` не NULL.
  - `test_archive_stale_events_skips_recent_event`:
    - Event с `starts_at = now - 3 days` (< threshold).
    - Returns 0, event остаётся `is_archived=False`.
  - `test_archive_stale_events_skips_resolved_event`:
    - Event с `starts_at = now - 10 days`, `result_outcome_id=<id>`, `is_archived=True` (правильный путь архивации через `set_result`).
    - Returns 0 (уже архивирован, не дублируем).
  - `test_archive_stale_events_skips_already_archived`:
    - Event с `starts_at = now - 10 days`, `result_outcome_id=None`, `is_archived=True` (теоретически возможно при ручной архивации админом).
    - Returns 0.
  - `test_archive_stale_events_custom_threshold`:
    - Event с `starts_at = now - 3 days`.
    - `service.archive_stale_events(threshold_days=2)` → returns 1.
    - Проверяет настраиваемость параметра.
- [ ] Использовать `nested_session`-фикстуру (SAVEPOINT) из `tests/integration/services/conftest.py`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая 2 новых.
- [ ] `uv run pytest tests/integration -m integration` — все integration, включая 5 новых.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - В psql: создать event с `starts_at = now() - interval '8 days', is_published=true, result_outcome_id=NULL`, и outcomes.
  - Через psql вызвать: `python -c "import asyncio; from src.shared.db import SessionLocal; from src.shared.services import EventService; async def m(): async with SessionLocal() as s: print(await EventService(s).archive_stale_events()); asyncio.run(m())"`. Должно вывести 1.
  - Проверить через psql: `select id, is_archived, archived_at from event where ...` — поле обновлено.
- [ ] Ветка `feature/TASK-018-scheduler-archive`, Conventional Commits:
  - `feat(repositories): EventRepository.archive_stale`
  - `feat(services): EventService.archive_stale_events`
  - `feat(scheduler): archive_stale_events job (daily 03:00 UTC)`
  - `test(integration): archive_stale_events (5 сценариев)`
  - `test(unit): archive_stale_events job + builder регистрация`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-018-report.md`, задача → `handoff/archive/TASK-018-scheduler-archive/task.md`.

## Артефакты

```
* src/shared/repositories/event.py                  # +archive_stale
* src/shared/services/event.py                      # +archive_stale_events
* src/bot/scheduler/jobs.py                         # +archive_stale_events job
* src/bot/scheduler/__init__.py                     # +archive_stale_events в __all__
* src/bot/scheduler/builder.py                      # +CronTrigger регистрация
+ tests/integration/services/test_event_service_archive_stale.py  # 5 тестов
+ tests/unit/bot/scheduler/test_archive_stale_events.py           # 2 теста
* tests/unit/bot/scheduler/test_builder.py          # +1 тест на регистрацию
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Фоновые задачи → Архивация (страховка)»
- [src/shared/services/event.py](../../src/shared/services/event.py) — `set_result` для образца архивации
- [src/shared/repositories/event.py](../../src/shared/repositories/event.py) — `set_result` repo-метод для образца
- [src/bot/scheduler/builder.py](../../src/bot/scheduler/builder.py) — текущий scheduler (TASK-017)
- [src/bot/scheduler/jobs.py](../../src/bot/scheduler/jobs.py) — `dispatch_reminders` для образца паттерна job

## Подсказки исполнителю

- **`CronTrigger(hour=3, minute=0)`** vs `IntervalTrigger(days=1)`. CronTrigger даёт точное время — «каждый день в 03:00 UTC». Interval — «каждые 24 часа от старта», то есть после рестарта бота время сдвинется. Cron надёжнее для daily-задач.
- **03:00 UTC** — выбрано как «тихое время» в большинстве часовых поясов. Если по факту окажется неудобно (например, нагрузка от других cron'ов на сервере) — поменяем без эффекта на код. Конфигурируемое значение через `Settings` сейчас НЕ нужно — преждевременно.
- **`misfire_grace_time=300`** для cron — щедрее чем у `dispatch_reminders` (60s). Архивация не критична ко времени: если scheduler пропустил окно из-за рестарта — пусть догонит в течение 5 минут.
- **Bulk-update vs цикл по строкам.** `UPDATE ... WHERE ...` одной командой быстрее и атомарнее, чем `SELECT id ... FROM ... → for row: UPDATE`. Не пытайся загружать события в Python — лишний трафик. См. `mark_correctness` в `PredictionRepository` для образца.
- **`archived_at=func.now()`** в repo — БД ставит текущее время, не Python. Это важно: если scheduler запускается на машине с разъехавшимся `datetime.now()`, БД даст правильное время.
- **`now` как параметр сервиса** — для тестов. Передавая explicit `now`, можно проверять «событие 7 дней назад архивируется, 6 дней — нет» детерминированно, без `freezegun`. Дефолт `datetime.now(tz=UTC)` для production.
- **`is_archived = false` в фильтре `WHERE`** — обязательно, иначе при следующем тике скрипт обновит уже архивированные события (записав новый `archived_at`). Не критично, но грязно.
- **Тесты `archive_stale` integration-уровня — на реальном Postgres.** Не sqlite. Используй фикстуру `nested_session` (SAVEPOINT) для отката.
- **`logger.info("scheduler.archive_stale.done", archived_count=count)`** — даже при count=0 логируем. Это даёт sysadmin'у sanity check «job отработал». Если хочется отдельный лог только при count > 0 — flag в `info`-stream'е.
- **Никакого audit-лога**: автоматическое действие, нет `admin_id`. Если когда-то понадобится — потребует расширения `AuditLog` модели (nullable `admin_id` или ENUM `actor`). Записывать в `BACKLOG` после review.

## Что НЕ делать

- Не делать notification пользователям при автоархивации — это страховка от потерянного итога, не достижение результата. Если пользователь увидит в «Мои прогнозы → Архив» событие с `is_correct = NULL` — он поймёт.
- Не настраивать порог `threshold_days` через `Settings` — преждевременно. Дефолт 7 в спеке.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости.
- Не зеркалить в Drive вручную.
- Не делать **обратный** путь («разархивировать») — это не предусмотрено спецификацией. Если админ опоздал, но всё-таки хочет зафиксировать итог — отдельная задача / админ-action.
