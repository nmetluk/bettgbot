---
task: TASK-018
type: question
created: 2026-05-24
agent: claude-code-local
status: blocked
---

# TASK-018 — вопрос: конфликт с CHECK-constraint `ck_event_result_archive_consistency`

## Суть

Спецификация TASK-018 требует архивировать события **без** зафиксированного итога:

> APScheduler-job ежедневно: помечает `is_archived = true` события, у которых `starts_at < now - 7 дней` и `result_outcome_id IS NULL` ...
> Эти события не дают пользователю прогнозировать, но видны в архиве **без** отметки «сбылся/нет» (NULL).

Но в `0001_init` миграции уже есть CHECK-constraint на таблице `event` (см. `src/shared/models/event.py:53-62`):

```python
CheckConstraint(
    "(result_outcome_id IS NULL AND is_archived = false) OR "
    "(result_outcome_id IS NOT NULL AND is_archived = true "
    "AND archived_at IS NOT NULL)",
    name="ck_event_result_archive_consistency",
),
```

Это запрещает комбинацию `is_archived = true AND result_outcome_id IS NULL`. И `docs/03-data-model.md` явно фиксирует инвариант:

> - `result_outcome_id IS NULL` ⇒ `is_archived = false`
> - `result_outcome_id IS NOT NULL` ⇒ `is_archived = true AND archived_at IS NOT NULL`

То есть task.md и spec data-model'и противоречат друг другу: новый «страховочный» путь архивации без итога **запрещён** существующим CHECK'ом.

Подтверждено локально: `UPDATE event SET is_archived = true WHERE result_outcome_id IS NULL` бросает `asyncpg.exceptions.CheckViolationError: ck_event_result_archive_consistency`.

## Что я уже сделал на ветке `feature/TASK-018-scheduler-archive` (не запушено)

1. `EventRepository.archive_stale(cutoff)` — bulk-update согласно спеке.
2. `EventService.archive_stale_events(now=None, threshold_days=7)` — обёртка с commit.
3. Job `archive_stale_events` в `src/bot/scheduler/jobs.py`.
4. Регистрация `CronTrigger(hour=3, minute=0)` в `build_scheduler`.
5. 2 unit-теста на job, обновлён `test_builder.py` под два job'а.

Эти куски не нарушают CHECK сами по себе — конфликт виден только в integration-тестах на реальном Postgres (см. `test_archive_stale_events_archives_old_unresolved_event` — `CheckViolationError`).

## Возможные пути решения

Прошу выбрать (либо предложить четвёртый).

### Вариант A: миграция `0003_relax_event_archive_constraint`

Расширить CHECK до трёх допустимых комбинаций:

```sql
ALTER TABLE event DROP CONSTRAINT ck_event_result_archive_consistency;
ALTER TABLE event ADD CONSTRAINT ck_event_result_archive_consistency CHECK (
    (result_outcome_id IS NULL AND is_archived = false AND archived_at IS NULL)
    OR (result_outcome_id IS NULL AND is_archived = true AND archived_at IS NOT NULL)
    OR (result_outcome_id IS NOT NULL AND is_archived = true AND archived_at IS NOT NULL)
);
```

Семантика теперь: «архивное событие — это event с `archived_at IS NOT NULL`; `result_outcome_id` опционален».

Минусы:
- Обновить `docs/03-data-model.md` (инварианты) — это зона cowork.
- Третий вариант валидной комбинации в data-model: «архивный без итога» — нужно явно описать в docs.

### Вариант B: «синтетический outcome» для непросроченных событий

Создать в каждом event при создании специальный outcome `no_result` (или похожее) и при автоархивации ставить `result_outcome_id = <его id>`.

Минусы:
- Засоряет таблицу `outcome`, нарушает её домен.
- `mark_correctness` в `PredictionRepository` помечает прогнозы как `is_correct = (outcome_id == correct_outcome_id)`. Если `correct_outcome_id` = `no_result`, то все прогнозы будут `is_correct = false`. Спец-кейсинг.
- Архивный список «Мои прогнозы → Архив» нужно учить отображать «no_result» как `⏳` (а не «сбылся/нет»). Это вырастает в кучу UI-логики.

Я считаю, что этот путь хуже A.

### Вариант C: оставить событие неархивированным, ограничить только в UI

Не делать UPDATE вообще. Вместо архивации в UI/handler'е скрывать события с `starts_at < now - 7d AND result_outcome_id IS NULL` из списка активных и каталога.

Минусы:
- Противоречит явному тексту task.md («помечает `is_archived = true`»).
- Каждый запрос «активные события» вынужден добавлять условие `OR (starts_at < now - 7d AND result_outcome_id IS NULL)` в исключение — лишняя везде.
- Не решает «событие висит в каталоге» — оно технически активно в БД.

### Вариант D: твой?

## Рекомендация

Вариант A. Это явное расширение data-model'и, изначально не предусмотренное; задача нового пути требует расширения инварианта. Под него — миграция `0003_relax_event_archive_constraint` (с обратимым downgrade'ом: archived без result → удалить или поставить `is_archived=false`; обратимость — на твоё усмотрение).

После решения смогу:
1. Добавить миграцию (отдельный шаг в DoD).
2. Включить и допилить 5 integration-тестов из task.md.
3. Запушить и слить.

## Ссылки

- `src/shared/models/event.py:53-62` — `CheckConstraint`
- `src/migrations/versions/0001_init.py` — миграция, где этот CHECK создавался
- `docs/03-data-model.md` — текущий инвариант (раздел `Event`)
- `handoff/inbox/TASK-018-scheduler-archive.blocked.md` — задача (переименована в blocked)
- Локальная ветка `feature/TASK-018-scheduler-archive` — частичная реализация (не запушена)

## Что я **не** делаю до ответа

- Не пушу `feature/TASK-018-scheduler-archive` — там зелёный mypy/ruff, но integration-тесты не запущены, ведь они блокируются конфликтом.
- Не открываю PR с реализацией.
- Не добавляю миграцию самовольно — это влияет на data-model и docs/, которые я не правлю без явного указания (CLAUDE.md).
- Жду `handoff/inbox/TASK-018-amendment.md`.
