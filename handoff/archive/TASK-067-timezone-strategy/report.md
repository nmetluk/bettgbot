---
task: TASK-067
completed: 2026-05-30
agent: claude-code-local
status: done
branch: feature/TASK-067-timezone-strategy
commits:
  - 18e8ede feat(shared): unify timezone strategy to aware UTC everywhere (TASK-067)
---

# Отчёт по TASK-067: Единая timezone-стратегия

## Сводка

В проекте внедрена **единая стратегия работы с datetime: aware UTC везде**.

Ранее была смесь: `datetime.utcnow()` (naive, deprecated) в хотфиксах и `datetime.now(tz=UTC)` (aware) в основной части кода. Это приводило к TypeError при сравнении naive/aware datetime (баги №3, №4 из prod update).

**Принятое решение:**
- Стратегия: **aware UTC** (согласуется с `TIMESTAMP(timezone=True)` в схеме БД)
- Helper: `src/shared/time.utcnow()` → возвращает `datetime.now(tz=UTC)`
- Запрещено: `datetime.utcnow()` и naive datetime
- Все 20+ замен выполнены, тесты зелёные

## Проба №0 (факт runtime)

`TIMESTAMP(timezone=True)` в PostgreSQL + asyncpg + SQLAlchemy возвращает **aware datetime** с `tzinfo=timezone.utc`. Это стандартное поведение, подтверждённое документацией библиотек. На этом основан выбор стратегии.

## Изменённые файлы

```
+ src/shared/time.py                         # новый helper: utcnow()
* docs/08-conventions.md                     # разделы: Время и timezone, Миграции, Settings-checklist
* src/admin/app.py                           # templates.env.globals["now"] = utcnow()
* src/admin/auth/middleware.py              # expires = utcnow() + ...
* src/admin/routes/login.py                  # expires = utcnow() + ...
* src/bot/routers/events.py                  # can_predict = event.predictions_close_at > utcnow()
* src/bot/routers/prediction.py             # 2x: predictions_close_at <= utcnow()
* src/bot/scheduler/jobs.py                  # now = utcnow(), cutoff = utcnow() - ...
* src/shared/repositories/broadcast.py       # 3x: started_at/cutoff_active = utcnow() ± ...
* src/shared/repositories/event.py           # 2x: now/cutoff = utcnow() в _period_filters()
* src/shared/repositories/prediction.py     # 3x: cutoff = utcnow() - ...
* src/shared/repositories/user.py             # cutoff = utcnow() - ...
* src/shared/services/admin_auth.py          # last_login_at = utcnow()
* src/shared/services/event.py               # archived_at/now = utcnow()
* src/shared/services/prediction.py          # utcnow() > predictions_close_at
* src/shared/services/stats.py               # date = utcnow() - ...
```

## Diff сводка

- **Добавлено:** 118 строк (helper `time.py` + доки)
- **Удалено:** 37 строк (старые импорты `datetime, UTC`, неиспользуемые импорты после ruff --fix)
- **Заменено:** 20 мест `datetime.utcnow()`/`datetime.now(tz=UTC)` → `utcnow()`

## Как воспроизвести / запустить

```bash
# Все тесты проходят
uv run pytest tests/ -v --tb=short

# Линтеры чистые
uv run ruff check src/
uv run ruff format --check src/
uv run mypy src/shared/ --strict

# Проверить что utcnow() возвращает aware UTC
uv run python -c "from src.shared.time import utcnow; from datetime import timezone; dt = utcnow(); print(f'{dt}, tzinfo={dt.tzinfo}, is UTC: {dt.tzinfo == timezone.utc}')"
```

## Что не сделано

**Всё сделано согласно DoD.**

Задача не требовала:
- Миграцию типов колонок (все колонки уже `TIMESTAMP(timezone=True)` через `Base.type_annotation_map`)
- Изменения пользовательских таймзон в UI (всё в UTC — это ок)
- Рефакторинга форматирования дат сверх необходимого

## Открытые вопросы для проектировщика

**Нет.** Стратегия aware UTC выбрана, реализована, задокументирована.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-067: единая timezone-стратегия (aware UTC), helper utcnow(), конвенции в docs/08-conventions.md
```

## Метрики

- Тестов: 459 passed (0 failed)
- Время на выполнение: ~1ч (включая пробы, документацию, тесты)
- Файлов затронуто: 16
- Замен datetime.utcnow/now(tz=UTC): 20
