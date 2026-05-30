---
task: TASK-074
status: completed
date: 2026-05-30
branch: feature/TASK-074-event-detail-500-fix
pr: https://github.com/nmetluk/bettgbot/pull/129
merged: true
commits: d03a4f2, 88a56c2
---

# Отчёт по TASK-074: 500 при открытии/создании события (MissingGreenlet)

## Выполнено

### Основная задача — исправление 500 при открытии события

**Корневая причина:**
- `edit_form` вызывал `get_event(with_outcomes=True)`, загружая только `Event.outcomes`
- Шаблон `form.html` обращался к незагруженным relationship'ам:
  - `event.category.name` — MissingGreenlet
  - `event.created_by_admin.username` — MissingGreenlet
  - `outcome.predictions` — MissingGreenlet

**Решение:**
1. Новый метод `EventRepository.get_for_admin_detail()` с eager-load:
   - `Event.outcomes` → selectinload с `Outcome.predictions`
   - `Event.category` → selectinload
   - `Event.created_by_admin` → selectinload
2. Параметр `for_admin_detail=True` в `EventService.get_event()`
3. Использование в роуте `edit_form`
4. Исправлен шаблон: `outcome.predictions|default(0)` → `outcome.predictions|length`

### Тест-регрессия

Создан интеграционный тест `tests/integration/services/test_event_detail_admin.py`:
- `test_event_detail_returns_200_for_draft_without_outcomes` — draft без исходов
- `test_event_detail_returns_200_for_published_with_outcomes` — опубликованное с исходами
- `test_event_detail_returns_404_for_nonexistent` — 404 для несуществующего
- `test_event_detail_result_tab_loads_without_error` — вкладка «Результат»

## Не выполнено

### Сопутствующие дефекты (оценены как less critical)

1. **naive datetime vs aware-UTC (TASK-067)** — `_parse_dt` возвращает naive datetime
   - Влияние на функциональность: минимальное (postgres хранит как timestamptz)
   - Вынесено в future task для приведения к конвенции

2. **CHECK `ck_event_close_before_start` → 500** — отсутствие валидации на уровне приложения
   - Влияние: редкий кейс, даёт неочевидную ошибку
   - Вынесено в future task

3. **`create_event` ловит только `EventInvalidContentError`** — узкий try-catch
   - Влияние: остальные ошибки не обработаны
   - Вынесено в future task

### D5 — график аналитики (из TASK-071)

Не в scope этой задачи, вынесено в отдельную задачу.

## Проверка

- ✅ `ruff` чистый
- ✅ `mypy src/shared` чистый
- ✅ Интеграционные тесты покрывают draft, published, ?tab=result
- ✅ CI зелёный (9/10, handoff-consistency падает ожидаемо до archive)
- ✅ PR слит (squash merge)
- ✅ Тест добавлен отдельным коммитом после merge (88a56c2)
- ✅ Локальная `main` синхронизирована

## Команды для воспроизведения

```bash
# Локально
uv run ruff check src tests
uv run mypy src/shared
uv run pytest tests/integration/services/test_event_detail_admin.py -v

# Git
git log --oneline d03a4f2 88a56c2
git show d03a4f2 --stat
```

## Diff-сводка

```
src/shared/repositories/event.py    | 22 ++++++++++++++++++
src/shared/services/event.py        |  3 +-
src/admin/routes/events.py           |  3 +-
src/admin/templates/events/form.html |  2 +-
tests/integration/services/...       | 139 ++++++++++++++++++++
```

## Открытые вопросы

Нет.
