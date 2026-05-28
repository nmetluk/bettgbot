# 02 — Технологический стек

Согласован 2026-05-22 по запросу владельца «твой выбор». Полное обоснование выбора — [ADR-0001](adr/0001-tech-stack.md).

## Выбранный стек

| Слой | Технология | Версия | Обоснование |
|---|---|---|---|
| Язык | Python | 3.12 | Современная асинхронность, типизация, зрелая экосистема для Telegram-ботов и веб-бэкенда |
| Telegram-бот | aiogram | 3.x | Async-first, FSM из коробки, активно поддерживается, понятный routing |
| Веб-фреймворк (админка) | FastAPI | 0.110+ | Async, DI, прекрасно сосуществует с SQLAlchemy 2.0, минимум boilerplate |
| Шаблонизатор | Jinja2 | 3.x | Стандарт для server-rendered Python; интегрируется с FastAPI |
| Интерактивность UI | HTMX | 1.9+ | Без SPA-сложности; точечные обновления страницы по ajax; идеально для минимальной админки |
| Клиентские состояния UI | Alpine.js | 3.x | Лёгкие клиентские тогглы (тема, плотность таблиц) без выхода на SPA; принято в [ADR 0005](adr/0005-admin-v2-stack.md) для админки v2 |
| CSS-фреймворк | Bootstrap | 5.3 | База компонентов; поверх — собственные дизайн-токены `--pv-*` из прототипа v2 (тема, плотность, акцент), см. [ADR 0005](adr/0005-admin-v2-stack.md) |
| ORM | SQLAlchemy | 2.0 (async) | Стандарт; типизация; единый API для бота и админки |
| Миграции | Alembic | 1.13+ | Стандартный спутник SQLAlchemy |
| БД | PostgreSQL | 16 | Транзакции, индексы по JSONB, надёжность, бэкапы стандартными средствами |
| FSM-storage / cache | Redis | 7 | Состояние aiogram FSM, антифлуд, лёгкое масштабирование |
| HTTP-клиент | httpx | 0.27+ | Async, нативный таймаут/ретрай, понятный API |
| Аутентификация админа | passlib[bcrypt] + itsdangerous | — | Bcrypt-хеш пароля + signed cookie для сессии |
| Планировщик задач | APScheduler | 3.x | Напоминания и архивация; запускается в bot-процессе как фоновая корутина |
| Тесты | pytest, pytest-asyncio, factory-boy, freezegun | — | Стандартный набор для проверки async-кода и фабрик моделей |
| Линт / формат | ruff | 0.4+ | Один инструмент вместо black/isort/flake8 |
| Типы | mypy | 1.10+ | strict для `src/shared/`, lenient для слоя хендлеров |
| Логирование | structlog | 24.x | Структурный JSON-лог + context binding |
| Контейнеризация | Docker + Docker Compose | — | Запуск всей системы одной командой |
| CI | GitHub Actions | — | Бесплатно для приватных репо в разумных лимитах; интегрируется с PR |
| Менеджер пакетов | uv (предпочтительно) или poetry | — | Финальный выбор — в TASK-002. uv быстрее и работает с pyproject.toml; poetry зрелее |

## Что НЕ используем (и почему)

| Что | Почему отказались |
|---|---|
| python-telegram-bot | Хороший фреймворк, но aiogram удобнее для async-first и FSM |
| Django + Django Admin | Дублирование стека (sync ORM рядом с async); монолитность; для минимальной админки переплата сложностью |
| SQLite | Допустимо для proto, но для нескольких тысяч пользователей и админских join-запросов PostgreSQL даёт лучший потолок |
| Реакт / Vue / любой SPA | В админке нет сложной интерактивности; HTMX закрывает потребности без отдельного билд-пайплайна |
| Celery | Для текущего объёма фоновых задач APScheduler внутри bot-процесса достаточно. Celery — потенциальная миграция в будущем |
| Pydantic v1 | Используем v2 (pydantic-settings v2) |

## Python: где живёт интерпретатор

В системе **нет** глобально установленного `python3.12` — Python ставит сам `uv` в свой кеш и подсовывает его в `.venv` репо. Это значит:

- Локально все Python-команды запускаются как `uv run <cmd>` или через `.venv/bin/python` (создан `uv sync`'ом).
- В CI Python тоже ставится через `astral-sh/setup-uv@v6` — отдельная установка через `actions/setup-python` не нужна.
- В Docker-образах будет использоваться официальный `python:3.12-slim` (или эквивалент), уже с системным Python — см. [07-deployment.md](07-deployment.md).

Репо при этом помечен как **сервис, не библиотека:** в `pyproject.toml` нет `[build-system]`, стоит `[tool.uv] package = false`. Пакеты `src.*` подключаются через `pythonpath = ["."]` (для pytest) и `PYTHONPATH=/app` (для Docker), а не через `pip install`. Обоснование — [ADR-0004](adr/0004-no-build-backend.md).

## Версии Python и базовые зависимости (исторический черновик)

> Финальный `pyproject.toml` и `uv.lock` уже сгенерированы в TASK-002 — смотри сами файлы. Ниже остаётся **исторический ориентир** того, что мы выбирали как минимальный стартовый набор. Не редактируй; правки идут в реальный `pyproject.toml`.

```toml
[project]
name = "bettgbot"
requires-python = ">=3.12"

dependencies = [
  "aiogram>=3.5,<4",
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "jinja2>=3.1",
  "sqlalchemy[asyncio]>=2.0",
  "alembic>=1.13",
  "asyncpg>=0.29",
  "redis>=5.0",
  "httpx>=0.27",
  "pydantic>=2.7",
  "pydantic-settings>=2.2",
  "passlib[bcrypt]>=1.7",
  "itsdangerous>=2.2",
  "apscheduler>=3.10",
  "structlog>=24.1",
]

[dependency-groups]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "factory-boy>=3.3",
  "freezegun>=1.5",
  "ruff>=0.4",
  "mypy>=1.10",
  "httpx>=0.27",   # уже есть, но нужен для тестов
]
```

## Конфигурация

- Все настройки — через переменные окружения (см. [`infra/.env.example`](../infra/.env.example) после создания).
- Парсинг — pydantic-settings; объект `Settings()` импортируется из `src/shared/config.py`.
- В Docker Compose значения приходят через `env_file`.

## Версионирование

- Python — фиксировано в `pyproject.toml` (`requires-python = ">=3.12"`).
- Зависимости — фиксированы lock-файлом (`uv.lock` или `poetry.lock`).
- Docker-образы — теги по semver (`bettgbot/bot:0.1.0`) + `latest` на main.

## Связанное

- [ADR-0001 tech stack](adr/0001-tech-stack.md)
- [07-deployment.md](07-deployment.md)
- [08-conventions.md](08-conventions.md)
