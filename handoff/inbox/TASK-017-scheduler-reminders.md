---
id: TASK-017
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md (раздел «Фоновые задачи → Рассылка напоминаний»)
  - docs/03-data-model.md
  - src/shared/services/reminder.py
  - src/shared/models/reminder_setting.py
  - src/bot/main.py
priority: high
estimate: L
---

# TASK-017: APScheduler-job рассылки напоминаний

## Контекст

**Первая фоновая задача в проекте.** До сих пор бот был чисто request-driven (handler → service → DB). Теперь нужен периодический job, который независимо от user-action ходит по событиям + настройкам напоминаний и шлёт пользователям сообщения.

Спецификация — [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md), раздел «Фоновые задачи → Рассылка напоминаний». Алгоритм каждые 5 минут:

1. Найти события `is_archived = false AND is_published = true` с `predictions_close_at > now()`.
2. Для каждого события — пользователей, у которых:
   - `reminder_setting.enabled = true`,
   - есть offset из `offsets_minutes`, попадающий в текущее окно относительно `predictions_close_at`,
   - **нет** `prediction` по этому событию,
   - **нет** записи в `reminder_dispatch_log(user_id, event_id, offset_minutes)` (дедупликация).
3. Отправить сообщение «До дедлайна по событию «{title}» осталось {humanized}» + кнопка/команда «Сделать прогноз».

`APScheduler` уже в зависимостях `pyproject.toml` (`apscheduler>=3.10,<4`). `AsyncIOScheduler` будем использовать (бот на asyncio).

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) раздел «Фоновые задачи».
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — модели `Event`, `ReminderSetting`, `Prediction`, `User`. Добавим новую — `ReminderDispatchLog`.
- [`src/shared/services/reminder.py`](../../src/shared/services/reminder.py) — текущий `ReminderService`, расширим.
- [`src/bot/main.py`](../../src/bot/main.py) — `build_dispatcher`, `main()` с polling. Добавим scheduler.
- [`src/shared/db.py`](../../src/shared/db.py) — `get_session` / sessionmaker, используется в middleware.
- [`docs/02-tech-stack.md`](../../docs/02-tech-stack.md) — APScheduler упомянут.

## Перед стартом — pre-task cleanup PR

В origin/main `ace0440` — last commit (archive TASK-016). **Working tree после моих review-правок:**

- `state/PROJECT_STATUS.md` — закрытие TASK-016, новый шаг TASK-017.
- `state/DECISIONS.md` — строка про стилевую норму handler-сигнатур.
- Новая сессия `sessions/2026-05-24-02-task-016-review/`.
- `handoff/inbox/TASK-017-scheduler-reminders.md` — эта задача.

Branch: `chore/post-TASK-016-cowork-cleanup`, PR `chore(handoff): post-TASK-016 review by cowork`. После merge — `feature/TASK-017-scheduler-reminders`.

## Цель

Бот, запущенный через `python -m src.bot.main`, параллельно polling крутит scheduler, который каждые 5 минут отправляет подходящим пользователям напоминания. Один пользователь не получает дубли (через `ReminderDispatchLog`). Покрыто integration-тестами на `find_candidates` (минимум 5 сценариев) + unit-тестами на job-функцию + smoke на сборку scheduler'а.

## Definition of Done

### Step 1 — Модель `ReminderDispatchLog` + миграция

- [ ] **Новый файл `src/shared/models/reminder_dispatch_log.py`:**
  ```python
  """Модель `ReminderDispatchLog` — дедупликация отправленных напоминаний."""

  from __future__ import annotations

  from datetime import datetime
  from typing import TYPE_CHECKING

  from sqlalchemy import BigInteger, ForeignKey, Integer, UniqueConstraint, func
  from sqlalchemy.orm import Mapped, mapped_column, relationship

  from .base import Base

  if TYPE_CHECKING:
      from .event import Event
      from .user import User


  class ReminderDispatchLog(Base):
      __tablename__ = "reminder_dispatch_log"
      __table_args__ = (
          UniqueConstraint(
              "user_id", "event_id", "offset_minutes",
              name="uq_reminder_dispatch_log_user_event_offset",
          ),
      )

      id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
      user_id: Mapped[int] = mapped_column(
          BigInteger,
          ForeignKey("user.id", ondelete="CASCADE", name="fk_reminder_dispatch_log_user_id_user"),
          nullable=False,
      )
      event_id: Mapped[int] = mapped_column(
          BigInteger,
          ForeignKey("event.id", ondelete="CASCADE", name="fk_reminder_dispatch_log_event_id_event"),
          nullable=False,
      )
      offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
      dispatched_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

      user: Mapped[User] = relationship()
      event: Mapped[Event] = relationship()

      def __repr__(self) -> str:
          return (
              f"<ReminderDispatchLog user_id={self.user_id} event_id={self.event_id} "
              f"offset={self.offset_minutes}>"
          )
  ```
- [ ] **Зарегистрировать в `src/shared/models/__init__.py`** — добавить импорт и в `__all__`.
- [ ] **Миграция `src/migrations/versions/0002_reminder_dispatch_log.py`** — `alembic revision --autogenerate -m "reminder_dispatch_log"`. Проверить, что Alembic корректно сгенерировал:
  - Создание таблицы.
  - Уникальный constraint `uq_reminder_dispatch_log_user_event_offset`.
  - Два FK CASCADE.
  - Опционально — `Index("ix_reminder_dispatch_log_dispatched_at", "dispatched_at")` для будущего cleanup. На MVP можно без, но запишите в `BACKLOG` если не делаете.
- [ ] **`make migrate`** — миграция применяется без ошибок. Откат `alembic downgrade -1` тоже работает.

### Step 2 — `ReminderDispatchLogRepository`

- [ ] **Новый файл `src/shared/repositories/reminder_dispatch_log.py`:**
  ```python
  """`ReminderDispatchLogRepository` — запись фактов отправки напоминаний."""

  from __future__ import annotations

  from sqlalchemy import select
  from sqlalchemy.dialects.postgresql import insert as pg_insert
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..models import ReminderDispatchLog

  __all__ = ["ReminderDispatchLogRepository"]


  class ReminderDispatchLogRepository:
      def __init__(self, session: AsyncSession) -> None:
          self._session = session

      async def was_dispatched(
          self, *, user_id: int, event_id: int, offset_minutes: int
      ) -> bool:
          stmt = select(ReminderDispatchLog.id).where(
              ReminderDispatchLog.user_id == user_id,
              ReminderDispatchLog.event_id == event_id,
              ReminderDispatchLog.offset_minutes == offset_minutes,
          )
          result = await self._session.execute(stmt)
          return result.scalar_one_or_none() is not None

      async def record(
          self, *, user_id: int, event_id: int, offset_minutes: int
      ) -> bool:
          """Возвращает True если вставка прошла, False если уже было (гонка).

          `on_conflict_do_nothing` защищает от двух одновременных вызовов из
          параллельных scheduler instance'ов (на MVP — не сценарий, но дёшево).
          """
          stmt = (
              pg_insert(ReminderDispatchLog)
              .values(user_id=user_id, event_id=event_id, offset_minutes=offset_minutes)
              .on_conflict_do_nothing(
                  constraint="uq_reminder_dispatch_log_user_event_offset"
              )
              .returning(ReminderDispatchLog.id)
          )
          result = await self._session.execute(stmt)
          return result.scalar_one_or_none() is not None
  ```
- [ ] **Зарегистрировать в `src/shared/repositories/__init__.py`** — импорт и в `__all__`.

### Step 3 — `ReminderService.find_candidates`

- [ ] **В `src/shared/services/reminder.py`** добавить:
  ```python
  from dataclasses import dataclass
  from datetime import datetime, timedelta


  @dataclass(frozen=True, slots=True)
  class ReminderCandidate:
      """Кандидат на отправку напоминания: один user × event × offset."""

      tg_user_id: int      # для bot.send_message
      user_id: int         # для record в dispatch_log
      event_id: int
      event_title: str
      offset_minutes: int
      predictions_close_at: datetime


  class ReminderService:
      # ... existing __init__, get, update, list_users_to_notify, _validate_offsets

      async def find_candidates(
          self, *, now: datetime, window_minutes: int = 5
      ) -> list[ReminderCandidate]:
          """Найти всех (user, event, offset), кому нужно отправить напоминание сейчас.

          Окно: для каждого `offset` берём события, у которых
          `now + offset <= predictions_close_at < now + offset + window_minutes`.

          Фильтры:
          - событие `is_published AND NOT is_archived`,
          - `reminder_setting.enabled = TRUE` И `offset_minutes @> ARRAY[offset]`,
          - НЕТ `prediction` для (user, event),
          - НЕТ `reminder_dispatch_log` для (user, event, offset).

          Возвращает плоский список кандидатов — handler/job уже не делает фильтрацию.
          """
  ```
  - **Реализация — один SQL с self-join на ARRAY-unnest** или несколько шагов:
    - Получить все события `is_published AND NOT is_archived AND predictions_close_at > now`.
    - Для каждого события — список уникальных `offset_minutes` из всех `ReminderSetting.offsets_minutes` (через `func.unnest`), у которых окно `(predictions_close_at - now)` в `[offset, offset + window_minutes)`.
    - Затем JOIN с `User × ReminderSetting` (где `enabled=true`), LEFT OUTER JOIN с `Prediction`, LEFT OUTER JOIN с `ReminderDispatchLog`, фильтр `WHERE prediction.id IS NULL AND dispatch_log.id IS NULL`.
  - **Если один SQL получается слишком сложным** — допустимо разбить на два шага в Python:
    - SQL #1: вернуть `[(event, [matching_offsets])]`.
    - Python: для каждого event × offset — SQL #2 вернуть подходящих пользователей.
    - Это O(N × M) SQL'ей, где N=активных событий, M=уникальных offset'ов. На MVP с десятком событий и парой offset'ов — ОК.
  - **Покрой docstring примером**: «`now = 12:00`, `event.predictions_close_at = 13:00`, `offset = 60` → окно `[60, 65)` минут, разница 60 минут попадает, кандидат включается». Это важно для понимания валидности окна.
- [ ] **Зарегистрировать `ReminderCandidate`** в `__all__`.

### Step 4 — Scheduler bootstrap

- [ ] **Новый файл `src/bot/scheduler/__init__.py`:**
  ```python
  """APScheduler bootstrap — фоновые задачи бота (TASK-017+)."""

  from .builder import build_scheduler
  from .jobs import dispatch_reminders

  __all__ = ["build_scheduler", "dispatch_reminders"]
  ```
- [ ] **Новый файл `src/bot/scheduler/builder.py`:**
  ```python
  """Фабрика `AsyncIOScheduler` с зарегистрированными job'ами."""

  from __future__ import annotations

  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  from apscheduler.triggers.interval import IntervalTrigger
  from sqlalchemy.ext.asyncio import async_sessionmaker

  from aiogram import Bot

  from .jobs import dispatch_reminders

  __all__ = ["build_scheduler"]


  def build_scheduler(
      *, bot: Bot, session_maker: async_sessionmaker
  ) -> AsyncIOScheduler:
      """Собирает scheduler с reminder-job каждые 5 минут.

      Использует UTC; misfire_grace_time=60s (если кто-то пропустит run по
      нагрузке/перезапуску — за minute догонит).
      """
      scheduler = AsyncIOScheduler(timezone="UTC")
      scheduler.add_job(
          dispatch_reminders,
          trigger=IntervalTrigger(minutes=5),
          kwargs={"bot": bot, "session_maker": session_maker},
          id="dispatch_reminders",
          replace_existing=True,
          misfire_grace_time=60,
      )
      return scheduler
  ```
- [ ] **Новый файл `src/bot/scheduler/jobs.py`** — само задание:
  ```python
  """Реализации scheduler-job'ов."""

  from __future__ import annotations

  from datetime import UTC, datetime

  from aiogram import Bot
  from aiogram.exceptions import TelegramAPIError
  from sqlalchemy.ext.asyncio import async_sessionmaker

  from src.shared.logging import get_logger
  from src.shared.repositories import ReminderDispatchLogRepository
  from src.shared.services import ReminderService

  from .. import keyboards, texts

  __all__ = ["dispatch_reminders"]


  logger = get_logger(__name__)


  async def dispatch_reminders(
      *, bot: Bot, session_maker: async_sessionmaker
  ) -> None:
      """Один тик scheduler'а: найти кандидатов и отправить им сообщения."""
      now = datetime.now(tz=UTC)
      async with session_maker() as session:
          service = ReminderService(session)
          candidates = await service.find_candidates(now=now, window_minutes=5)
          dispatch_log = ReminderDispatchLogRepository(session)

          for cand in candidates:
              # Идемпотентность: пробуем зафиксировать ДО send_message.
              # Если другая инстанция scheduler'а уже отправила — record вернёт False.
              recorded = await dispatch_log.record(
                  user_id=cand.user_id,
                  event_id=cand.event_id,
                  offset_minutes=cand.offset_minutes,
              )
              if not recorded:
                  continue

              try:
                  await bot.send_message(
                      cand.tg_user_id,
                      texts.REMINDER_NOTIFICATION.format(
                          title=cand.event_title,
                          humanized=keyboards.humanize_minutes(cand.offset_minutes),
                          close_at_fmt=cand.predictions_close_at.strftime("%d.%m %H:%M"),
                      ),
                      reply_markup=keyboards.main_menu(),
                  )
                  logger.info(
                      "scheduler.reminder.sent",
                      user_id=cand.user_id,
                      event_id=cand.event_id,
                      offset_minutes=cand.offset_minutes,
                  )
              except TelegramAPIError as exc:
                  # Пользователь заблокировал бота / удалил аккаунт.
                  # Не откатываем dispatch_log: повторно слать смысла нет.
                  logger.warning(
                      "scheduler.reminder.send_failed",
                      user_id=cand.user_id,
                      event_id=cand.event_id,
                      offset_minutes=cand.offset_minutes,
                      error=str(exc),
                  )

          await session.commit()
  ```

### Step 5 — Интеграция в `src/bot/main.py`

- [ ] **Обновить `src/bot/main.py`:**
  ```python
  from src.shared.db import session_maker  # export ensure в src/shared/db.py
  from .scheduler import build_scheduler


  async def main() -> None:
      s = get_settings()
      configure_logging(s.log_level, s.log_format)
      logger.info("bot.startup", log_format=s.log_format)

      bot, dp = build_dispatcher()
      scheduler = build_scheduler(bot=bot, session_maker=session_maker)
      scheduler.start()
      logger.info("scheduler.started", jobs=[j.id for j in scheduler.get_jobs()])

      try:
          await bot.delete_webhook(drop_pending_updates=True)
          await dp.start_polling(bot)
      finally:
          scheduler.shutdown(wait=True)
          closer = getattr(dp["registry"], "close", None)
          if callable(closer):
              await closer()
          await bot.session.close()
          logger.info("bot.shutdown")
  ```
- [ ] **`src/shared/db.py`** — проверить, что `session_maker` экспортируется (или экспортировать его). Сейчас там вероятно `engine` + `get_session` async-генератор. Нужен явный `async_sessionmaker[AsyncSession]` для scheduler, потому что job не работает в контексте FastAPI/aiogram middleware.
  ```python
  from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine

  engine = create_async_engine(...)
  session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
      engine, expire_on_commit=False
  )

  async def get_session() -> AsyncIterator[AsyncSession]:
      async with session_maker() as session:
          yield session
  ```
  - Если `session_maker` уже есть — оставь как есть; если нет — выдели.

### Step 6 — Тексты

- [ ] **В `src/bot/texts.py`** добавить:
  ```python
  REMINDER_NOTIFICATION = (
      "🔔 Напоминание!\n\n"
      "До приёма прогнозов по событию <b>«{title}»</b> осталось <b>{humanized}</b>.\n"
      "Дедлайн: <b>{close_at_fmt}</b>.\n\n"
      "Сделать прогноз: /events"
  )
  ```
- [ ] Обнови `__all__`.

### Step 7 — Тесты

#### `tests/integration/services/test_reminder_service_find_candidates.py` (новый)

Использует `nested_session`-фикстуру (SAVEPOINT) из `tests/integration/services/conftest.py` (если она там; иначе — `session`-фикстуру с rollback).

- [ ] `test_find_candidates_user_with_matching_offset_returns_candidate`
  - Setup: User с `ReminderSetting(enabled=True, offsets_minutes=[60])`, Event с `predictions_close_at = now + 62 min`, нет prediction, нет dispatch_log.
  - Assert: `find_candidates(now=now, window_minutes=5)` вернул 1 кандидата с `offset_minutes=60`.
- [ ] `test_find_candidates_disabled_setting_excluded`
  - `enabled=False` → пусто.
- [ ] `test_find_candidates_offset_outside_window_excluded`
  - `offsets_minutes=[60]`, `predictions_close_at = now + 70 min` (за пределами `[60, 65)`) → пусто.
- [ ] `test_find_candidates_with_prediction_excluded`
  - User + matching event + offset, но есть `Prediction` → пусто.
- [ ] `test_find_candidates_already_dispatched_excluded`
  - User + matching event + offset, есть `ReminderDispatchLog(user, event, 60)` → пусто.
- [ ] `test_find_candidates_archived_event_excluded`
  - Event `is_archived=True` → пусто.
- [ ] `test_find_candidates_unpublished_event_excluded`
  - Event `is_published=False` → пусто.
- [ ] `test_find_candidates_multiple_offsets_returns_only_matching`
  - User с `offsets_minutes=[60, 1440]`, event с `predictions_close_at = now + 62 min`. Возвращает 1 кандидата `offset=60`, не два.

#### `tests/unit/bot/scheduler/test_dispatch_reminders.py` (новый)

- [ ] `test_dispatch_reminders_sends_message_and_records_log` (mocks: `find_candidates` возвращает 1 кандидата, `dispatch_log.record` → True, `bot.send_message` — `AsyncMock`).
- [ ] `test_dispatch_reminders_skips_already_recorded` (`record` → False, `send_message` не вызывается).
- [ ] `test_dispatch_reminders_logs_telegram_error_but_continues` (`send_message` бросает `TelegramAPIError`, остальные кандидаты обрабатываются).

#### `tests/unit/bot/scheduler/test_builder.py` (новый, smoke)

- [ ] `test_build_scheduler_registers_dispatch_reminders_job` — `build_scheduler(...)` возвращает `AsyncIOScheduler`, у которого один job с `id="dispatch_reminders"`, trigger — `IntervalTrigger(minutes=5)`.

#### `tests/integration/test_migrations.py` (расширение)

- [ ] Добавить тест `test_0002_creates_reminder_dispatch_log` (или подобный) — проверяет, что после `alembic upgrade head` таблица существует, уникальный constraint на месте.

### Step 8 — `ReminderDispatchLog` в integration-conftest

- [ ] Если в `tests/integration/conftest.py` или `tests/integration/services/conftest.py` есть фикстуры `category`, `event`, `outcome`, `prediction` — добавь по аналогии фикстуру `reminder_dispatch_log` (или factory) для будущих тестов. На MVP — не обязательно, можно создавать прямо в тесте.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit.
- [ ] `uv run pytest tests/integration -m integration` — все integration, включая новые.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `make up && make migrate` — миграция применилась.
  - В psql: создать тестового user'а с `tg_user_id`, `reminder_setting.offsets_minutes={5}`, `event(predictions_close_at = now() + 7 minutes)`.
  - `uv run python -m src.bot.main` — в логах появится `scheduler.started`. Через 5 минут — `scheduler.reminder.sent`. В Telegram пользователь получит сообщение.
- [ ] Ветка `feature/TASK-017-scheduler-reminders`, Conventional Commits:
  - `feat(models): ReminderDispatchLog + миграция 0002`
  - `feat(repositories): ReminderDispatchLogRepository`
  - `feat(services): ReminderService.find_candidates + ReminderCandidate dataclass`
  - `feat(scheduler): AsyncIOScheduler + dispatch_reminders job`
  - `feat(texts): REMINDER_NOTIFICATION`
  - `feat(bot): scheduler в main() параллельно polling`
  - `test(integration): find_candidates 8 сценариев`
  - `test(unit): scheduler builder + dispatch_reminders job`
  - `test(integration): migration 0002 reminder_dispatch_log`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-017-report.md`, задача → `handoff/archive/TASK-017-scheduler-reminders/task.md`.

## Артефакты

```
+ src/shared/models/reminder_dispatch_log.py         # модель
* src/shared/models/__init__.py                      # +ReminderDispatchLog
+ src/migrations/versions/0002_reminder_dispatch_log.py
+ src/shared/repositories/reminder_dispatch_log.py
* src/shared/repositories/__init__.py                # +ReminderDispatchLogRepository
* src/shared/services/reminder.py                    # +ReminderCandidate + find_candidates
* src/shared/services/__init__.py                    # +ReminderCandidate в __all__
* src/shared/db.py                                   # export session_maker (если ещё нет)
+ src/bot/scheduler/__init__.py
+ src/bot/scheduler/builder.py
+ src/bot/scheduler/jobs.py
* src/bot/main.py                                    # build_scheduler + start/shutdown
* src/bot/texts.py                                   # +REMINDER_NOTIFICATION
+ tests/integration/services/test_reminder_service_find_candidates.py  # 8 тестов
+ tests/unit/bot/scheduler/test_dispatch_reminders.py # 3 теста
+ tests/unit/bot/scheduler/test_builder.py            # 1 smoke
* tests/integration/test_migrations.py                # +миграция 0002
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Фоновые задачи → Рассылка напоминаний»
- [src/shared/services/reminder.py](../../src/shared/services/reminder.py)
- [src/shared/repositories/prediction.py](../../src/shared/repositories/prediction.py) — образец `pg_insert + on_conflict_do_nothing/update` (TASK-007)
- [src/shared/models/reminder_setting.py](../../src/shared/models/reminder_setting.py) — образец модели с FK + ARRAY-полем
- [src/shared/services/event.py](../../src/shared/services/event.py) — образец сервиса с composition репозиториев (для `find_candidates` будут join'ы)
- [src/bot/main.py](../../src/bot/main.py) — текущий entry-point
- [tests/integration/services/test_event_service.py](../../tests/integration/services/test_event_service.py) — образец integration-теста с реальным postgres

## Подсказки исполнителю

- **AsyncIOScheduler vs BlockingScheduler.** Используй `AsyncIOScheduler` — бот на asyncio, scheduler crucially должен жить в том же event loop. `BlockingScheduler` запустит свой поток и не сможет вызывать корутины напрямую.
- **`misfire_grace_time=60` в `add_job`.** Если scheduler упустил time slot (например, рестарт бота на 2 минуты), он догонит при следующем тике. 60 секунд — допустимый дрейф.
- **Идемпотентность через `dispatch_log.record` ДО `send_message`.** Это критично: если порядок инвертирован, при сбое после send_message пользователь получит дубль на следующем тике. Текущий порядок: «зарезервировал место в логе → отправил». Если send_message упал — мы НЕ откатываем log, потому что повторная отправка тому же user'у через 5 минут не имеет смысла (момент уже пропущен).
- **`on_conflict_do_nothing` в record.** Защищает от двух scheduler'ов, запущенных параллельно (MVP-сценарий — один инстанс, но дёшево). Возвращает `True` если запись прошла, `False` если конфликт.
- **`find_candidates` SQL может быть сложным.** Если один запрос становится 30+ строк — лучше разбить на два:
  ```python
  # шаг 1: события + matching offsets через unnest(offsets_minutes)
  # шаг 2: для каждого event × offset — пользователи без prediction и dispatch_log
  ```
  Это O(N×M) SQL, но при N=10 событий × M=2 offsets — 20 запросов раз в 5 минут. Безболезненно для MVP.
- **Окно `[offset, offset + window_minutes)`.** Граница исключающая справа: чтобы при `window_minutes=5` и offset=60 не пересекалось с offset=65 окно `[65, 70)`. Покрой тестом explicitly.
- **`ARRAY @> ARRAY[N]`** в SQLAlchemy: `ReminderSetting.offsets_minutes.contains([offset])`. Или через `func.array_position(...)`. Если pgsql-специфичный синтаксис мешает — `func.unnest(ReminderSetting.offsets_minutes)` и join.
- **`session_maker` — module-level singleton.** Не пересоздавай его в job — это разрушит connection pool. Импортируй один раз в `builder.py` или прокидывай через kwarg как сейчас.
- **`async with session_maker() as session`** в job: scheduler не имеет middleware, поэтому session создаётся вручную. `commit()` — в конце job, после всех `record()` (один транзакционный «батч»).
- **Бот может быть заблокирован пользователем.** `bot.send_message` бросит `TelegramAPIError` (или `TelegramForbiddenError`). Логируем warning, не падаем, идём к следующему кандидату. `dispatch_log` остаётся записанным — повторно слать нет смысла.
- **Тестировать scheduler без реального APScheduler-runtime.** Unit-тесты на `dispatch_reminders` создают `bot=AsyncMock(spec=Bot)` и `session_maker=...` (returning AsyncMock). Не запускай `scheduler.start()` в тестах — это лишняя ceremony, MVP не требует.
- **Integration-тесты используют реальный Postgres** через docker-compose (как в TASK-009 services). См. `tests/integration/services/test_event_service.py` для образца setup'а фикстур.
- **`datetime.now(tz=UTC)`** — обязательно `tz=UTC` (правило `docs/08-conventions.md`).
- **Логирование structured:** `logger.info("scheduler.reminder.sent", user_id=..., event_id=..., offset_minutes=...)`. Не f-строки. По правилам `docs/08-conventions.md`.

## Что НЕ делать

- Не реализовывать архивацию событий — это TASK-018.
- Не делать сложный admin UI для просмотра `reminder_dispatch_log` — это TASK-026 (audit-лог).
- Не пытаться сделать «exactly-once» доставку с retry — TG API без идемпотентного ключа, делаем «at-most-once» через dispatch_log. Если сообщение не дошло — пользователь сам зайдёт через `/events`.
- Не добавлять Redis-блокировки на job (для multi-instance) — MVP запускает один инстанс. Если когда-нибудь нужен HA — отдельная задача.
- Не делать cleanup старых `dispatch_log` записей в этом TASK — таблица будет расти линейно с активностью; через год оценим объём и решим (через TTL-job или партиции). Записать в `BACKLOG`.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости — `apscheduler` уже есть.
- Не зеркалить в Drive вручную — это зона cowork.
