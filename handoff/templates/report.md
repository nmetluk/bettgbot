---
task: TASK-NNN
completed: YYYY-MM-DD
agent: claude-code-local
status: done           # done | partial | blocked
pr: https://github.com/<owner>/<repo>/pull/NN
branch: feature/TASK-NNN-slug
commits:
  - <sha> feat: ...
---

# Отчёт по TASK-NNN: <тот же заголовок, что в задаче>

## Сводка

Два-три абзаца: что сделано, какие принятые решения внутри задачи (если их нужно зафиксировать), как это вписывается в общую картину.

## Изменённые файлы

```
+ src/shared/models/event.py            # новый, модель Event
+ src/migrations/versions/0003_events.py
* src/shared/models/__init__.py          # добавлен экспорт Event
+ tests/unit/test_event_model.py
```

## Как воспроизвести / запустить

```bash
# применить миграции
alembic upgrade head

# прогнать тесты
pytest tests/unit/test_event_model.py -v
```

## Что не сделано (если применимо)

Если что-то урезано относительно изначальной задачи — здесь подробно: что вынесено, почему, что предлагается сделать дальше (готов кандидат на новую задачу `TASK-NNN+1`).

## Открытые вопросы для проектировщика

- Вопрос 1: …
- Вопрос 2: …

Если нет вопросов — секцию можно оставить пустой с пометкой «нет».

## Предложение для PROJECT_STATUS.md

Готовая строка (или несколько), которые cowork-агент впишет в раздел «Сделано» в [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md):

```markdown
- 2026-MM-DD — TASK-NNN: модель `Event` и миграция `0003_events` (PR #NN)
```

## Метрики (опционально)

- Тестов добавлено: N
- Покрытие изменённых модулей: NN%
- Время на выполнение: ~Xч
