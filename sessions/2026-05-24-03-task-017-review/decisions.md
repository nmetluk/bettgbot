# Решения — task-017-review

**Все 5 — keep:**

| # | Решение | Альтернативы | Обоснование |
|---|---|---|---|
| 1 | `User.is_blocked = FALSE` в `find_candidates` — оставляем (исполнитель добавил по своей инициативе) | Слать всем (включая заблокированных) — TG-API вернёт ошибку | Не было в моей task-спеке явно, но добавление правильное: не нагружаем TG-API, не растим количество `TelegramForbiddenError` в логах. Покрыто integration-тестом `test_find_candidates_blocked_user_excluded`. Если когда-нибудь админ-юзер «разблокирован» — кандидаты появятся в следующем тике |
| 2 | mypy-override `[[tool.mypy.overrides]] module = ["apscheduler.*"]` с `ignore_missing_imports = true` — keep | `# type: ignore[import-untyped]` на каждом `import apscheduler.*` | У `apscheduler` нет `py.typed`, поэтому mypy strict ругается. Точечные ignore — шумнее в коде; project-wide override в pyproject — чище и легче снять, если когда-нибудь у пакета появится `py.typed`. Стандартный паттерн |
| 3 | `SessionLocal` остаётся именем `async_sessionmaker` в `src/shared/db.py` — keep | Переименовать в `session_maker` (как было в моей task-спеке) | Имя `SessionLocal` уже использовалось до TASK-017 (вероятно из TASK-006/007); локальный CC сохранил консистентность, не стал плодить refactor. Я в spec'е написал `session_maker` по привычке SQLAlchemy-tutorial'а, но это была моя неточность — приоритет за тем, что уже в коде |
| 4 | `REMINDER_NOTIFICATION` форматирует `predictions_close_at` в UTC через `strftime("%d.%m %H:%M")` — keep как MVP | Локализация по таймзоне пользователя | Локализация по TZ требует решения по источнику (явный выбор? IP-геолокация? UTC по умолчанию?) и формату (день недели? относительные «через 2 часа»?). Отдельная задача после согласования. На MVP UTC приемлемо |
| 5 | `TelegramAPIError` одним `except` — keep | Отдельная ветка на `TelegramForbiddenError` для метрики «бот заблокирован» | Минимальный обработчик: warning + переход к следующему кандидату. Если понадобится метрика — добавим `isinstance(exc, TelegramForbiddenError)` в обработчике без структурных изменений |
