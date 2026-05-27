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
3. **Транзакции — в сервисе.** Repository выполняет операции в переданной сессии; commit решает сервис. Rollback **не делает** — это работа контекст-менеджера сессии (middleware закроет с откатом при исключении).
4. **Внешний мир — только через интерфейсы.** Telegram API (через aiogram), HTTP — через `httpx` адаптеры, время — через `datetime.now(tz=UTC)` (никаких `datetime.utcnow()`), генерация id — через uuid.
5. **Идемпотентность.** Любой обработчик, который пишет в БД, проектируется так, чтобы повторный вызов с тем же входом не плодил дублей (uniq-constraints + upsert).
6. **Логирование — структурное.** `logger = structlog.get_logger(__name__)`. Каждое значимое событие — отдельный `info()/warning()/error()` с полями, не f-строкой.
7. **Бизнес-исключения — доменные классы** в `src/shared/exceptions.py`, не `ValueError`. Handler ловит их и форматирует ответ.

## Импорты и пакетная структура

### `src/` — полноценный пакет, не namespace

В корне `src/` лежит `__init__.py` (пустой). Это значит, что `src` — обычный пакет, и **все импорты во всём репо абсолютные через `src.*`**:

```python
from src.shared.config import settings
from src.shared.models import Event
from src.bot.middlewares import LoggingMiddleware
```

Это устраняет неоднозначность для mypy («одно и то же имя через разные пути»): без `src/__init__.py` `bot/main.py` мог бы видеть `from src.shared.logging`, а `shared/__init__.py` — `from .logging`, и mypy спотыкается. С пакетом — одно каноническое имя `src.shared.logging`.

В тестах — тот же стиль: `from src.shared.repositories import ...`. **Никаких relative-импортов выше одного уровня** (`from ..shared` внутри `src/shared/...` — ок, `from ..bot` из `src/admin/...` — нет, используй абсолютный `from src.bot...`).

### Side-effects в пакетных `__init__.py`

Некоторые пакеты в `src/shared/` имеют side-effects при импорте `__init__.py` — фабрики с `@lru_cache`, инициализация коннекций, чтение конфига. Пример: `src/shared/external/__init__.py` создаёт singleton-клиент через `get_registry_client()`, который дёргает `Settings`.

**Правило:** если нужен только тип (например, `ExternalUserRegistryClient` Protocol для аннотации параметра конструктора сервиса) — импортируй **из подмодуля** напрямую, не из пакета:

```python
# хорошо — берём только тип, side-effects __init__ не трогаем:
from src.shared.external.registry import ExternalUserRegistryClient, VerificationResult

# плохо — пакетный __init__ при импорте создаст фабрику и тронет settings:
from src.shared.external import ExternalUserRegistryClient, get_registry_client
```

Импортируй из пакета только когда **реально нужна** фабрика (в `main.py` бота/админки, где singleton-клиент собирается один раз на процесс).

### Фабрики читают свежий конфиг

Фабрики типа `get_registry_client()` и сборочные функции типа `build_dispatcher()` берут конфиг через `get_settings()`, **не через module-level `settings`**:

```python
# хорошо — каждый вызов фабрики получает актуальный Settings:
def build_dispatcher() -> tuple[Bot, Dispatcher]:
    s = get_settings()
    bot = Bot(token=s.telegram_bot_token.get_secret_value(), ...)
    ...

# плохо — module-level `settings` зафиксирован на момент импорта;
# `get_settings.cache_clear()` в тестах не подхватится:
from src.shared.config import settings
def build_dispatcher():
    bot = Bot(token=settings.telegram_bot_token.get_secret_value(), ...)
```

Хендлеры и сервисы могут пользоваться module-level `settings` (он singleton через `@lru_cache`) — там нет необходимости перечитывать конфиг. Правило про `get_settings()` касается именно фабрик, которые тесты должны иметь возможность пересобрать со свежим env.

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

## Security scanning в CI (TASK-040)

CI запускает 4 parallel security-job'а на каждый push/PR в `main`:

| Job | Инструмент | Что проверяет | Fail при |
|-----|-----------|---------------|----------|
| `security-sast` | [bandit](https://bandit.readthedocs.io/) | Python code на инъекции, weak crypto, leaks | HIGH/CRITICAL |
| `security-deps` | [pip-audit](https://pypi.org/project/pip-audit/) | Зависимости на известные CVE | Любой уязвимости |
| `security-secrets` | [gitleaks](https://github.com/gitleaks/gitleaks) | Секреты в коде (токены, пароли) | Любой совпадении |
| `scan-web/bot` | [trivy](https://trivy.dev/) | Docker images на CVE | HIGH/CRITICAL |

Дополнительно раз в неделю (каждое воскресенье 04:00 UTC) запускается `security-image-scan.yml` — глубокий scan Docker-образов.

### Reaction на findings

**SAST (bandit):**
- Если это **реальная проблема** → фиксим в отдельном PR.
- Если **false-positive** → добавляем в `pyproject.toml [tool.bandit]` `skips`/`assert_used`.

**Dependencies (pip-audit):**
- CVE в transitive-зависимости → обновляем пакет (`uv pip add <package>@latest`).
- Если upstream не пофиксил → открываем TASK с описанием, временно игнорируем через comment.

**Secrets (gitleaks):**
- **НИКОГДА не игнорировать** реальные секреты. Rotate немедленно.
- False-positive (тестовые токены) → `.gitleaks.toml` `allowlist`.

**Images (trivy):**
- HIGH/CRITICAL в base image (`python:3.12-slim`) → ожидаемо, но документируем.
- HIGH/CRITICAL в runtime deps (`aiogram`, `httpx`, etc.) → обновляем.

### Dependabot

`.github/dependabot.yml` настроен:
- **pip**: еженедельно (воскресенье), группирует patch/minor обновления в один PR.
- **docker**: еженедельно, обновляет base images.
- **github-actions**: еженедельно, обновляет workflow actions.

Обновления зависимостей **блокируют merge** только если они связаны с security (через grouping).

## Документация в коде

- Каждый модуль начинается с короткого `"""..."""` — назначение в 1–3 строки.
- Сложные функции (>20 строк) — с docstring (что делает, контракты).
- Никаких комментариев-«объяснений того, что и так видно». Только «почему» и инварианты.

## Связанное

- [01-architecture.md](01-architecture.md), [02-tech-stack.md](02-tech-stack.md)
- [handoff/README.md](../handoff/README.md) — git flow согласован с handoff-протоколом
