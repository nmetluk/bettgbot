# 08 — Кодовые конвенции

Документ задаёт «единый стиль» проекта: структура модулей, naming, форматирование, типизация, git, тесты. Применяется ко всему `src/` и `tests/`.

## Структура `src/`

```
src/
├── bot/
│   ├── __init__.py
│   ├── main.py                 # entrypoint: aiogram Dispatcher, polling
│   ├── routers/                # отдельный Router на каждый раздел (events, prediction, my, reminders, help, start)
│   │   ├── start.py
│   │   ├── events.py
│   │   ├── prediction.py
│   │   ├── my.py
│   │   ├── reminders.py
│   │   └── help.py
│   ├── keyboards/              # сборка ReplyKeyboardMarkup / InlineKeyboardMarkup
│   ├── states.py               # FSM-states
│   ├── middlewares/            # logging, user-injection, rate-limit
│   ├── scheduler/              # APScheduler jobs (reminders, archive)
│   └── texts.py                # все строки UI
├── admin/
│   ├── app.py                  # FastAPI()
│   ├── deps.py                 # DI: current_admin, db_session
│   ├── auth/
│   ├── routes/                 # один файл на раздел
│   ├── templates/
│   └── static/
├── shared/
│   ├── __init__.py
│   ├── config.py               # pydantic-settings, Settings
│   ├── db.py                   # async engine, sessionmaker, get_session
│   ├── logging.py              # structlog настройка
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── event.py
│   │   ├── outcome.py
│   │   ├── prediction.py
│   │   ├── reminder_setting.py
│   │   ├── admin_user.py
│   │   └── audit_log.py
│   ├── repositories/           # один файл на агрегат: user, category, event, prediction, audit
│   ├── services/               # бизнес-логика: user, event, prediction, stats, reminder, audit
│   ├── external/               # ExternalUserRegistryClient + реализации
│   └── exceptions.py           # доменные исключения: NotAllowedError, DeadlineError, ...
└── migrations/
    ├── env.py
    ├── script.py.mako
    └── versions/
        └── 0001_init.py
```

## Naming

- **Модули:** `snake_case`. Подкаталоги под доменные группы.
- **Классы:** `PascalCase`. Имена сущностей строго из [GLOSSARY](../state/GLOSSARY.md).
- **Функции/методы/переменные:** `snake_case`.
- **Константы:** `UPPER_SNAKE_CASE`.
- **Приватное:** префикс `_`.
- **Async-функции** не помечаются префиксом — async очевиден из сигнатуры; контекст определяет вызывающий.
- **Имена тестов:** `test_<unit>_<scenario>_<expected>`. Файлы — `test_<module>.py`.

## Стиль кода

- **Форматтер и линтер:** `ruff` (включает изоляцию импортов, форматирование, набор lint-правил). Конфиг в `pyproject.toml`.
- **Длина строки:** 100.
- **Импорты:**
  1. stdlib
  2. сторонние библиотеки
  3. `src.*` (абсолютные импорты, никаких relative выше одного уровня)
- **Docstrings:** все публичные модули, классы, функции. Стиль — Google.
- **Типизация:** **обязательна** для всего `src/shared/`; для слоя хендлеров — обязательны типы параметров/возврата на публичных функциях.
  - `mypy --strict` для `src/shared/`.
  - `mypy` без `--strict` для `src/bot/` и `src/admin/`.
- **`Any` запрещён** в `src/shared/services/` без явного комментария-обоснования.

## Архитектурные правила

1. **Не лезть в БД из handlers/routes.** Handler ↔ Service ↔ Repository ↔ Model. Тестируется на ревью.
2. **Не лезть в сервисы из моделей.** Модели — только schema. Без бизнес-методов.
3. **Транзакции — в сервисе.** Repository выполняет операции в переданной сессии; commit/rollback решает сервис.
4. **Внешний мир — только через интерфейсы.** Telegram API (через aiogram), HTTP — через `httpx` адаптеры, время — через `datetime.now(tz=UTC)` (никаких `datetime.utcnow()`), генерация id — через uuid.
5. **Идемпотентность.** Любой обработчик, который пишет в БД, проектируется так, чтобы повторный вызов с тем же входом не плодил дублей (uniq-constraints + upsert).
6. **Логирование — структурное.** `logger = structlog.get_logger(__name__)`. Каждое значимое событие — отдельный `info()/warning()/error()` с полями, не f-строкой.
7. **Бизнес-исключения — доменные классы** в `src/shared/exceptions.py`, не `ValueError`. Handler ловит их и форматирует ответ.

## Git workflow

- **Ветки:**
  - `main` — стабильная, защищена.
  - `feature/TASK-NNN-<slug>` — фича одной задачи.
  - `fix/TASK-NNN-<slug>` — багфикс по задаче.
  - `chore/TASK-NNN-<slug>` — инфраструктура.
- **Коммиты:** [Conventional Commits](https://www.conventionalcommits.org/).
  - `feat(bot): add /reminders command`
  - `fix(admin): handle empty outcomes on publish`
  - `chore(ci): add ruff job`
  - `docs(arch): clarify mock-registry behavior`
  - `refactor(shared): extract PredictionService.mark_predictions`
  - `test(prediction): cover deadline edge case`
- Один PR — одна задача. Имя PR: `TASK-NNN: <subject>`. Описание PR ссылается на `handoff/inbox/TASK-NNN.md` и `handoff/outbox/TASK-NNN-report.md`.
- Squash merge в `main`. Сообщение мёрджа — заголовок Conventional + ссылка на PR.

## Тесты

- **Unit** (`tests/unit/`): сервисы, репозитории с in-memory SQLite или фейками, чистые функции. Быстрые, не требуют контейнеров.
- **Integration** (`tests/integration/`): с реальным PostgreSQL (docker-compose `db` + `redis` testcontainers или pre-started). Тестируют сценарии целиком — handler → service → DB.
- **Покрытие:** на MVP не задаём жёсткий порог; обязательно покрываем сервисы (`src/shared/services/`) и критические сценарии (регистрация, прогноз, фиксация итога, напоминания).
- **Фабрики:** `factory-boy`, в `tests/factories/`.
- **Время:** `freezegun` где нужно зафиксировать `now()`.

## Pre-commit

Конфиг `.pre-commit-config.yaml` (TASK-002):

- `ruff check --fix`
- `ruff format`
- `mypy src/shared/`
- (опционально) `pytest tests/unit -q` — если не сильно тормозит

## Документация в коде

- Каждый модуль начинается с короткого `"""..."""` — назначение в 1–3 строки.
- Сложные функции (>20 строк) — с docstring (что делает, контракты).
- Никаких комментариев-«объяснений того, что и так видно». Только «почему» и инварианты.

## Связанное

- [01-architecture.md](01-architecture.md), [02-tech-stack.md](02-tech-stack.md)
- [handoff/README.md](../handoff/README.md) — git flow согласован с handoff-протоколом
