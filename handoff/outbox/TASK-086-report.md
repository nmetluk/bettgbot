---
task: TASK-086
completed: 2026-05-31
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/161
branch: feature/TASK-086-dispatch-reminders-crash-safe-commits
commits:
  - d8bf79e feat(bot): TASK-086 dispatch_reminders crash-safe batched commits (M2 audit)
---

# Отчёт по TASK-086: dispatch_reminders — crash-safe commit-границы (без дублей напоминаний при рестарте)

## Сводка

Реализован **crash-safe паттерн** по точному образцу `dispatch_broadcasts` (и фикса из amendment TASK-061).

- Добавлен параметр `commit_batch_size: int = 50` (дефолт совпадает с broadcasts).
- Кандидаты материализуются в `list()` **до** цикла отправок (защита от ленивой выборки + mid-tick commit'ов, как указано в подсказке задачи).
- После каждого `record() + send/TelegramError` — счётчик; при достижении batch — `await session.commit()` + reset.
- Финальный commit для остатка батча.
- В `builder.py` — явная передача kwarg (документирует намерение).
- Обновлён docstring job'а.
- Новый integration-тест: 3 кандидата + batch=2 + повторный вызов с тем же `now` → 0 дублей. Тест **падал бы** на старой single-commit реализации (коммент в коде теста).

Идемпотентность (`record` строго ДО `send_message`, ON CONFLICT DO NOTHING) и обработка ошибок Telegram — без изменений.

## Коммиты и PR
- PR #161 (auto-merge включён)
- Коммит: d8bf79e

## Изменённые файлы
```
* src/bot/scheduler/jobs.py          # основное изменение + docstring
* src/bot/scheduler/builder.py       # вызов с явным commit_batch_size
* tests/integration/test_reminder_misfire_catchup.py  # новый тест
```

## Как воспроизвести / запустить
```bash
# unit (моки, быстро)
uv run pytest tests/unit/bot/scheduler/test_dispatch_reminders.py -q

# integration (реальный PG, проверяет batch + idempotency после "рестарта")
uv run pytest tests/integration/test_reminder_misfire_catchup.py::test_dispatch_reminders_crash_safe_with_batch_commits -q --tb=short

# в прод/стейджинге: рестарт бота посреди окна 5-минутного тика — дубли напоминаний больше не приходят.
```

## Что не сделано (если применимо)
- Не добавлял новое поле в `Settings` (reminder_commit_batch_size) — S-задача, дефолт 50 + явный kwarg в builder достаточно (как для broadcasts). При необходимости tunable — отдельный чейндж.
- Не трогал unit-тесты (они используют моки и продолжают работать через default-параметр).

## Открытые вопросы для проектировщика
Нет.

## Предложение для PROJECT_STATUS.md
```markdown
- 2026-05-31 — **TASK-086 закрыт:** dispatch_reminders теперь crash-safe (батчевые commit'ы + материализация кандидатов, M2 аудита). commit_batch_size=50 по образцу dispatch_broadcasts. Новый integration-тест на restart-дубли. PR #161.
```

## Метрики (опционально)
- Тестов добавлено: 1 (integration, exercises новый путь)
- Время: ~35 мин (анализ паттерна + минимальный дифф + тест)
