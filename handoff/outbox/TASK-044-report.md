---
task: TASK-044
completed: 2026-05-26
---

# TASK-044: Зафиксировать семантику счётчиков на дашборде

## Что сделано

Добавлен расширенный docstring к `DashboardService.get_counters()` в `src/shared/services/dashboard.py`:

```python
async def get_counters(self) -> dict[str, int]:
    """Счётчики объектов в БД для главной страницы админки.

    Все счётчики возвращают total без фильтров — админу нужна полная
    картина системы, а не «видимое из бота» подмножество.

    Returns:
        dict с ключами:
          - users — все пользователи, включая заблокированных
            (`is_blocked=true`). Удалённых нет — soft-delete не реализован.
          - events — все события, включая черновики (`is_published=false`)
            и архивные (`is_archived=true`).
          - categories — все категории, включая неактивные (`is_active=false`).
          - predictions — все прогнозы, в т.ч. по архивным событиям.

    Note:
        Запросы выполняются последовательно (4 простых COUNT-а). См.
        `state/DECISIONS.md` от 2026-05-26 — concurrent ops на одной
        AsyncSession в SQLAlchemy запрещены.
    """
```

Добавлены inline-комментарии про дефолтные параметры репозиториев:
- `events` — `# status="all" by default`
- `categories` — `# include_inactive=True by default`

## Что не сделано

Ничего — задача выполнена полностью.

## Открытые вопросы

Нет.

## Команды для воспроизведения

```bash
# Запуск тестов дашборда
uv run pytest tests/ -k dashboard -v

# Проверка линтера
uv run ruff check src/shared/services/dashboard.py
```

## Diff-сводка

- `src/shared/services/dashboard.py` — расширен docstring, добавлены 2 inline-комментария

## Артефакты

- PR: https://github.com/nmetluk/bettgbot/pull/86
- Squash-коммит: `docs(dashboard): fix counters semantics in get_counters() docstring`
