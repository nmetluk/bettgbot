---
id: TASK-002
created: 2026-05-22
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - pyproject.toml
  - docs/02-tech-stack.md
  - docs/08-conventions.md
priority: high
estimate: M
---

# TASK-002: Финализация инструментария — uv, pre-commit, CI

## Контекст

После TASK-001 у нас есть пустой git-репозиторий с документацией и заготовкой `pyproject.toml`, но никаких реально установленных зависимостей, lock-файла, hook-ов и CI. Эта задача — закрыть «инструментарий разработки» до того, как мы начнём писать бизнес-код.

Стек подтверждён в [ADR-0001](../../docs/adr/0001-tech-stack.md). Кодовые конвенции — в [docs/08-conventions.md](../../docs/08-conventions.md). Заготовка `pyproject.toml` уже содержит ориентировочные версии и секции для ruff/mypy/pytest.

## Цель

В репозитории есть установленный, воспроизводимый Python-проект (uv), pre-commit hooks для ruff и mypy, и минимальный CI-workflow на GitHub Actions, который зелёный на пустом скелете.

## Definition of Done

- [ ] Выбран `uv` как пакетный менеджер (поставить локально через `brew install uv` или скрипт от Astral). Если по какой-то причине uv не ставится — обосновать переход на poetry в отчёте и оформить ADR-0004; не делать выбор молча.
- [ ] `pyproject.toml` финализирован:
  - сборочный backend — `hatchling` (как и в заготовке) или `setuptools` на выбор исполнителя; обосновать в отчёте, если меняем
  - точные версии (минимум `>=` нижние границы из заготовки, верхние границы для major-bump-чувствительных библиотек)
  - все секции `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` из заготовки сохранены и протестированы
- [ ] Сгенерирован `uv.lock` (или `poetry.lock` в случае fallback), закоммичен.
- [ ] Создана минимальная структура пакетов в `src/`:
  - `src/shared/__init__.py` (пустой, с docstring)
  - `src/bot/__init__.py` (пустой)
  - `src/admin/__init__.py` (пустой)
  - удалить соответствующие `.gitkeep`
- [ ] `ruff check src tests` — зелёный.
- [ ] `ruff format --check src tests` — зелёный.
- [ ] `mypy src/shared` — зелёный (на пустом пакете тривиально, проверяем что mypy ставится и читает конфиг).
- [ ] `pytest` — зелёный (нет тестов → exit 0 с `--strict-config`, либо добавить один smoke-тест `tests/unit/test_smoke.py` с `def test_smoke(): assert True`).
- [ ] `.pre-commit-config.yaml` создан со стадиями:
  - `ruff check --fix`
  - `ruff format`
  - `mypy src/shared`
  - (опционально, если не сильно тормозит) `pytest tests/unit -q`
- [ ] `pre-commit install` выполнен; коммит автоматически проходит через хуки.
- [ ] GitHub Actions workflow `.github/workflows/ci.yml`:
  - триггеры: `push` в любую ветку и `pull_request` в `main`
  - jobs: `lint` (ruff check + ruff format --check), `typecheck` (mypy src/shared), `test` (pytest)
  - все три на `ubuntu-latest`, Python 3.12, кеш зависимостей через `astral-sh/setup-uv@v3` или эквивалент
  - все три зелёные на пустом скелете
- [ ] Ветка `feature/TASK-002-tooling`, коммиты по Conventional Commits, PR в `main` открыт. Если branch protection отсутствует (см. [state/DECISIONS.md](../../state/DECISIONS.md)) — всё равно идём через PR. Merge — squash; merge делает владелец после ревью, либо агент с явного разрешения в отчёте.
- [ ] Отчёт `handoff/outbox/TASK-002-report.md` написан по шаблону.
- [ ] Задача перемещена в `handoff/archive/TASK-002-tooling/task.md`.

## Артефакты

```
* pyproject.toml                       # финализирован (точные версии, build-backend)
+ uv.lock                              # новый
+ .pre-commit-config.yaml              # новый
+ .github/workflows/ci.yml             # новый
+ src/shared/__init__.py               # новый (взамен .gitkeep)
+ src/bot/__init__.py                  # новый (взамен .gitkeep)
+ src/admin/__init__.py                # новый (взамен .gitkeep)
- src/shared/.gitkeep                  # удалён
- src/bot/.gitkeep                     # удалён
- src/admin/.gitkeep                   # удалён
+ tests/unit/test_smoke.py             # опционально, если pytest без тестов падает
```

## Ссылки

- [docs/02-tech-stack.md](../../docs/02-tech-stack.md) — стек и набор зависимостей
- [docs/08-conventions.md](../../docs/08-conventions.md) — конвенции (ruff/mypy/git/тесты/pre-commit)
- [ADR-0001 tech stack](../../docs/adr/0001-tech-stack.md)
- [pyproject.toml](../../pyproject.toml) — заготовка для финализации

## Подсказки исполнителю

- **uv**: установка `curl -LsSf https://astral.sh/uv/install.sh | sh` или `brew install uv`. Инициализация — `uv sync` (создаст `.venv` и `uv.lock`). Не нужно `uv init`, `pyproject.toml` уже есть.
- **mypy на пустом пакете**: добавь в `src/shared/__init__.py` docstring `"""Shared package: models, repositories, services, external clients, config."""` и `__all__: list[str] = []`. Этого хватит, чтобы mypy в strict-режиме не ругался.
- **pytest без тестов**: по умолчанию exit code 5 (`no tests collected`). В `pyproject.toml` уже есть `addopts = "-ra -q"`. Либо добавь `--strict-config` и игнорируй exit 5 в CI, либо проще — положи smoke-тест.
- **GitHub Actions кеш**: `astral-sh/setup-uv@v3` сам делает кеш по `uv.lock`. Не изобретай свой.
- **mypy в pre-commit**: запускать как локальный hook (`language: system`), а не через `mirrors-mypy`, чтобы видеть те же зависимости, что и в `uv sync`. Пример:
  ```yaml
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run mypy src/shared
        language: system
        pass_filenames: false
        types: [python]
  ```
- **PR-template** из TASK-001 уже создан. Используй его при открытии PR.

## Что НЕ делать

- Не добавлять зависимости, которых нет ни в [docs/02-tech-stack.md](../../docs/02-tech-stack.md), ни в заготовке `pyproject.toml`. Если что-то реально нужно — спрашивай через `outbox/TASK-002-question.md`.
- Не писать никакого бизнес-кода (моделей, сервисов, обработчиков). Это задачи TASK-005 и далее.
- Не настраивать deployment workflow (Docker build/push, deploy via SSH) — это TASK-026/TASK-029.
- Не редактировать `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
