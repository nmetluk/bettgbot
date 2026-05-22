# ADR 0004 — Репо как сервис: без build-backend, `[tool.uv] package = false`

**Status:** Accepted
**Date:** 2026-05-23
**Deciders:** local Claude Code (исходное решение в TASK-002), cowork-agent + owner (формализация)

## Context

При финализации `pyproject.toml` в [TASK-002](../../handoff/archive/TASK-002-tooling/task.md) встал вопрос о выборе build-backend (заготовка предлагала `hatchling`, альтернатива — `setuptools`, `poetry-core`). Этот вопрос не самостоятельный: build-backend нужен только если репозиторий собирается в распространяемый артефакт (wheel/sdist), который ставится через `pip install`.

Реальные сценарии репо `bettgbot`:

- Локальная разработка — `uv sync` в venv, запуск через `uv run python -m src.bot.main`.
- Тесты — `uv run pytest` с `pythonpath = ["."]`.
- CI — то же самое (`uv sync --frozen` → `uv run ...`).
- Деплой ([docs/07-deployment.md](../07-deployment.md)) — Docker Compose; в Dockerfile планируется `COPY src /app/src` и запуск `python -m src.bot.main` напрямую, без `pip install`.

Ни один из сценариев не требует ни wheel-артефакта, ни публикации в PyPI, ни установки пакета через pip. Build-backend для них — холостая ceremony.

## Decision

- **Build-backend не используется.** Секция `[build-system]` в `pyproject.toml` отсутствует.
- **`[tool.uv] package = false`** — явно говорим `uv`, что репозиторий не является устанавливаемым пакетом; `uv sync` ставит только зависимости в `.venv`, не пытается собирать сам проект.
- **`src.*` подключается через `PYTHONPATH`.** Для pytest задано `[tool.pytest.ini_options] pythonpath = ["."]`. Для CLI-запуска используется `uv run python -m src.<...>`, который автоматически прокидывает корень в `sys.path`. Для Docker — `PYTHONPATH=/app` плюс `WORKDIR /app`.

## Alternatives considered

| Альтернатива | Почему отвергнуто |
|---|---|
| **`hatchling` + `[tool.hatch.build.targets.wheel] packages = ["src/bettgbot"]`** | Потребовал бы single top-level package (например, переименовать `src/{bot,admin,shared}` в `src/bettgbot/{bot,admin,shared}` либо `[tool.hatch.build.targets.wheel] sources = {"src" = ""}`). Изменение импортов ради сборочного артефакта, которого мы не используем |
| **`setuptools` с `[tool.setuptools.packages.find]`** | Та же избыточность: setuptools нужен для wheel; wheel мы не собираем |
| **Оставить hatchling из заготовки, но `uv sync` упадёт** | uv по умолчанию пытается сбилдить и установить корневой пакет. Либо нужен build-backend, либо `package = false`. Решение «и build-backend, и не собирать на самом деле» нелогично |
| **Использовать `pip install -e .` в Dockerfile** | Это всё равно требует build-backend; единственный выигрыш — `import src` доступен без правки PYTHONPATH. Стоит ceremony меньше, чем `PYTHONPATH=/app` плюс одна переменная окружения |

## Consequences

**Положительные:**

- `pyproject.toml` короче и сфокусирован на dependency management, без секций сборки.
- `uv sync` отрабатывает быстро — не пытается компилить корневой пакет.
- Структура `src/{bot,admin,shared,migrations}` остаётся плоской, без обёрточного `src/bettgbot/`.
- Понятная ментальная модель: «это сервис, который запускается, а не библиотека, которую устанавливают».

**Отрицательные / риски:**

- **Dockerfile-ы должны включать `PYTHONPATH=/app`** (или эквивалент). Это нужно зафиксировать в [docs/07-deployment.md](../07-deployment.md) при финализации Docker-файлов (TASK-003 / TASK-026).
- **Если когда-нибудь захотим публиковать пакет** (CLI-утилита, библиотека для другого сервиса) — придётся вернуть build-backend и, скорее всего, переструктурировать `src/`. Это будет отдельный осознанный шаг с пересмотром этого ADR.
- **Некоторые сторонние инструменты** (например, `tox`, классические `editable installs` через старые pip) ожидают наличие build-backend. Мы их не используем; если появятся — оценим точечно.

## Влияние на другие документы

- [docs/02-tech-stack.md](../02-tech-stack.md) — пометить, что Python ставится `uv`'ом, нет глобального `python3.12`; пример pyproject обновить под текущую форму.
- [docs/07-deployment.md](../07-deployment.md) — при финализации `Dockerfile.bot` / `Dockerfile.web` зафиксировать `ENV PYTHONPATH=/app` или эквивалент.

## Related

- [TASK-002 task](../../handoff/archive/TASK-002-tooling/task.md), [TASK-002 report](../../handoff/outbox/TASK-002-report.md)
- [ADR 0001 — tech stack](0001-tech-stack.md)
- [`../02-tech-stack.md`](../02-tech-stack.md)
