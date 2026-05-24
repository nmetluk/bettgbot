---
task: TASK-018
type: amendment
created: 2026-05-24
author: cowork-agent
in-reply-to: handoff/outbox/TASK-018-question.md
---

# TASK-018 — поправка: Вариант A принят, расширяем инвариант

## Контекст

Спасибо за блокер — нашёл реальное противоречие между `docs/04-bot-flows.md` (требует «архивный без итога») и `docs/03-data-model.md` + CHECK `ck_event_result_archive_consistency` (запрещает). При проектировании TASK-018 я не сверился с инвариантом — моя ошибка.

**Решение: Вариант A (релакс инварианта через миграцию `0003`).**

Обоснование: расширение data-model'и явное и минимальное; один новый CHECK с тремя комбинациями вместо двух; семантика чистая — «`is_archived = true` ⇔ `archived_at IS NOT NULL`»; `result_outcome_id` становится независимой колонкой.

Я **уже обновил** `docs/03-data-model.md` (раздел `Event`): расширил список инвариантов до трёх валидных комбинаций, добавил параграф «История инварианта» со ссылкой на эту миграцию. Эти правки попадут в **этот же** PR как часть TASK-018 (по правилу `CLAUDE.md`: «docs трогаем только в стандартном pre-task cleanup PR» — но pre-task cleanup для TASK-018 уже был в PR #49 ([commit `c3d4816`](https://github.com/nmetluk/bettgbot/commit/c3d4816)), и docs там не было; теперь правки docs/03 живут в working tree).

## Дополнительные шаги (вставляются ПЕРЕД существующими Step 1-7 из task.md)

### Step 0 — Pre-task cleanup PR (повторный)

В origin/main `2a425ff` — последний коммит (block TASK-018). **Working tree содержит правки cowork**, которых нет в origin:

- `docs/03-data-model.md` — расширен инвариант Event до 3 комбинаций (см. выше).
- `state/PROJECT_STATUS.md` — статус «TASK-018 разблокирован, Вариант A принят».
- `state/DECISIONS.md` — строка про релакс инварианта.
- Новая сессия `sessions/2026-05-24-04-task-018-block-resolution/`.
- `handoff/inbox/TASK-018-amendment.md` — этот файл.

Branch: `chore/post-TASK-018-block-resolution-cleanup`, PR `chore(handoff): TASK-018 block resolution — relax archive invariant`. После merge — продолжаешь работу на существующей ветке `feature/TASK-018-scheduler-archive` (она была не запушена и содержит частичную реализацию).

### Step 1 — Миграция `0003_relax_event_archive_constraint`

- [ ] **Создать `src/migrations/versions/0003_relax_event_archive_constraint.py`** руками (не autogenerate — он не понимает CHECK-релакс корректно):
  ```python
  """relax event archive invariant: allow archived without result.

  Revision ID: 0003_relax_event_archive
  Revises: 0002_reminder_dispatch_log
  Create Date: 2026-05-24
  """

  from __future__ import annotations

  from alembic import op

  revision = "0003_relax_event_archive"
  down_revision = "0002_reminder_dispatch_log"
  branch_labels = None
  depends_on = None


  _OLD_CHECK = (
      "(result_outcome_id IS NULL AND is_archived = false) OR "
      "(result_outcome_id IS NOT NULL AND is_archived = true "
      "AND archived_at IS NOT NULL)"
  )

  _NEW_CHECK = (
      "(result_outcome_id IS NULL AND is_archived = false AND archived_at IS NULL) "
      "OR (result_outcome_id IS NULL AND is_archived = true AND archived_at IS NOT NULL) "
      "OR (result_outcome_id IS NOT NULL AND is_archived = true AND archived_at IS NOT NULL)"
  )


  def upgrade() -> None:
      op.drop_constraint("ck_event_result_archive_consistency", "event", type_="check")
      op.create_check_constraint(
          "ck_event_result_archive_consistency", "event", _NEW_CHECK
      )


  def downgrade() -> None:
      """Откат — возвращает старый строгий CHECK.

      ВНИМАНИЕ: downgrade упадёт, если в БД есть события «архивные без итога»
      (т.е. строки, для которых страховочный путь архивации уже сработал).
      В таком случае оператор должен сначала вручную решить, что делать
      с такими событиями: либо вручную проставить result_outcome_id, либо
      раз-архивировать, либо удалить — в зависимости от бизнес-намерения.
      """
      op.drop_constraint("ck_event_result_archive_consistency", "event", type_="check")
      op.create_check_constraint(
          "ck_event_result_archive_consistency", "event", _OLD_CHECK
      )
  ```
  - `down_revision = "0002_reminder_dispatch_log"` — проверь по `alembic current` / своей `0002`-ревизии.
  - Текст downgrade'а — комментарий в docstring; код не пытается auto-fix данные, потому что бизнес-логика «что делать с старыми архивными без итога» — не техническая.
- [ ] `make migrate` применяется без ошибок.
- [ ] `alembic downgrade -1` — отрабатывает на пустой БД (без архивных-без-итога). Тест-кейс «downgrade падает при таких строках» **не нужен** — задача downgrade'а fail-loud в этом случае.

### Step 2 — Обновить `CheckConstraint` в `src/shared/models/event.py`

- [ ] Заменить:
  ```python
  CheckConstraint(
      "(result_outcome_id IS NULL AND is_archived = false) OR "
      "(result_outcome_id IS NOT NULL AND is_archived = true "
      "AND archived_at IS NOT NULL)",
      name="ck_event_result_archive_consistency",
  ),
  ```
  на:
  ```python
  CheckConstraint(
      "(result_outcome_id IS NULL AND is_archived = false AND archived_at IS NULL) "
      "OR (result_outcome_id IS NULL AND is_archived = true AND archived_at IS NOT NULL) "
      "OR (result_outcome_id IS NOT NULL AND is_archived = true AND archived_at IS NOT NULL)",
      name="ck_event_result_archive_consistency",
  ),
  ```
- Модель и миграция должны синхронизироваться (см. правило в `docs/08-conventions.md`).

### Step 3 — Расширить `test_migrations.py`

- [ ] Добавить тест `test_0003_relax_event_archive_check`:
  - После `alembic upgrade head` создаём событие с `result_outcome_id=NULL, is_archived=true, archived_at=now()` — должно проходить (раньше упало бы с `CheckViolationError`).
  - Создаём событие с `result_outcome_id=NULL, is_archived=true, archived_at=NULL` — должно упасть (инвариант «archived ⇒ archived_at IS NOT NULL»).

### Step 4 — Существующие Step 1-7 из исходной TASK-018

Шаги 1-7 из [`handoff/inbox/TASK-018-scheduler-archive.blocked.md`](TASK-018-scheduler-archive.blocked.md) (или `handoff/archive/...` если уже перенесли) применяются без изменений. Часть уже сделана локально на `feature/TASK-018-scheduler-archive`:

- ✅ `EventRepository.archive_stale(cutoff)` — есть.
- ✅ `EventService.archive_stale_events(now, threshold_days=7)` — есть.
- ✅ Job `archive_stale_events` в `src/bot/scheduler/jobs.py` — есть.
- ✅ Регистрация `CronTrigger(hour=3, minute=0)` в `build_scheduler` — есть.
- ✅ 2 unit-теста на job, обновлён `test_builder.py` — есть.
- ⏸️ 5 integration-тестов на сервис — **доделать после миграции 0003** (сейчас падают с `CheckViolationError`).

### Step 5 — Запустить полную регрессию

- [ ] `uv run pytest -m "not integration"` — все unit зелёные.
- [ ] `uv run pytest tests/integration -m integration` — все integration зелёные, включая 5 новых из `test_event_service_archive_stale.py` и 1 новый из `test_migrations.py`.

## Что переехало в общую DoD

- Conventional commits — добавить:
  - `docs(data-model): расширить инвариант Event до 3 комбинаций (relax archive constraint)`
  - `feat(migrations): 0003_relax_event_archive_constraint`
  - `feat(models): обновить CheckConstraint Event под новый инвариант`
  - (далее существующие коммиты по Step 4)
- PR Title остаётся: `TASK-018: APScheduler-job автоматической архивации стейлевых событий`. В описании добавь упоминание Variant A и ссылку на `sessions/2026-05-24-04-task-018-block-resolution/`.

## Что я **не** делаю

- Не правлю `docs/04-bot-flows.md` — там уже корректно описан «архивный без отметки сбылся/нет». Конфликт был только в `docs/03-data-model.md`.
- Не добавляю в `BACKLOG.md` тех-долг — расширение чистое.
- Не правлю `src/shared/services/event.py.set_result` — он использует «нормальный путь» (с outcome_id), CHECK по-прежнему гарантирует, что без outcome_id нельзя архивировать через этот путь. Релакс затрагивает только новый job-путь.

## Ссылки

- [`handoff/outbox/TASK-018-question.md`](../outbox/TASK-018-question.md) — твой вопрос.
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — обновлённый инвариант (раздел `Event`).
- [`sessions/2026-05-24-04-task-018-block-resolution/`](../../sessions/2026-05-24-04-task-018-block-resolution/) — сессия разбора блокера.
- [`handoff/inbox/TASK-018-scheduler-archive.blocked.md`](TASK-018-scheduler-archive.blocked.md) — исходная задача (если ещё в inbox).

## Что дальше

После merge cleanup-PR и доделки TASK-018:
1. Открой PR `TASK-018: ...` с полной реализацией (миграция + модель + сервис + scheduler + тесты).
2. Дождись CI зелёного.
3. Отчёт `handoff/outbox/TASK-018-report.md` — упомяни блокер и разрешение через Variant A.
4. Архив → `handoff/archive/TASK-018-scheduler-archive/{task.md, amendment.md, question.md}` (все три в одну папку).
