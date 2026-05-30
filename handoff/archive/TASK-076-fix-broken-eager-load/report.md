---
task: TASK-076
completed: 2026-05-30
agent: cowork-agent
status: done
pr: https://github.com/nmetluk/bettgbot/pull/134
branch: feature/TASK-076-fix-broken-eager-load
commits:
  - cecb539 TASK-076: fix broken eager-load (class-bound loader option)
---

# Отчёт по TASK-076: 500 на деталях события — строковая loader-опция (ArgumentError)

## Сводка

Исправлен баг в `EventRepository.get_for_admin_detail`: строковая loader-опция `selectinload("predictions")`
заменена на class-bound атрибут `selectinload(Outcome.predictions)`.

SQLAlchemy 2.0 не принимает строки для имён атрибутов в loader options — `ArgumentError` при построении запроса.

## Изменённые файлы

```
* src/shared/repositories/event.py  # Outcome.predictions class-bound
* handoff/archive/TASK-076-fix-broken-eager-load/task.md
* handoff/archive/TASK-076-fix-broken-eager-load/TASK-076-report.md
```

## Как воспроизвести / запустить

```bash
# интеграционные тесты (реальный postgres)
pytest tests/integration -m integration -v
```

## Что не сделано

- Оптимизация `outcome.predictions|length` (агрегат-counts вместо загрузки коллекции) — не блокер, вынесена при необходимости.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-076: исправлен eager-load (class-bound loader option, #134)
```
