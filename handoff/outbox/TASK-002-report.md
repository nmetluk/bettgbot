---
task: TASK-002
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/2
branch: feature/TASK-002-tooling
commits:
  - c02dea1 chore(deps): finalize pyproject.toml and lock dependencies with uv
  - 53ea91a chore(scaffold): replace .gitkeep with package __init__.py and smoke test
  - 08fa17d chore(ci): add pre-commit hooks and GitHub Actions workflow
  - 4b90924 chore(handoff): mark TASK-002 in-progress
  # squash-merge → bb89808 на main
---

# Отчёт по TASK-002: Финализация инструментария — uv, pre-commit, CI

## Сводка

Инструментарий разработки закрыт целиком. Финализирован `pyproject.toml` (верхние границы версий, `requires-python = ">=3.12,<3.13"`), сгенерирован `uv.lock` через `uv sync` — venv и зависимости воспроизводимы. Из заготовки убран `[build-system]` и добавлен `[tool.uv] package = false`: репо — это сервис, не библиотека для PyPI, wheel мы не собираем, а `src.*` пакеты подключаются по PYTHONPATH (через `[tool.pytest.ini_options] pythonpath = ["."]`). Это явное расхождение с дефолтом заготовки — обоснование ниже в открытых вопросах.

Скаффолд `src/`: вместо трёх `.gitkeep` лежат настоящие `__init__.py` с docstring уровня модуля (`shared`, `bot`, `admin`). `src/shared/__init__.py` дополнительно содержит `__all__: list[str] = []`, чтобы mypy strict не ругался на пустой пакет. Добавлен smoke-тест `tests/unit/test_smoke.py`, который заодно проверяет, что путь `src.shared` импортируется.

Подключён `.pre-commit-config.yaml` с тремя локальными хуками через `uv run` (ruff check --fix, ruff format, mypy src/shared) — `language: system`, чтобы видеть те же зависимости, что в `uv.lock`. `pre-commit install` выполнен. Создан `.github/workflows/ci.yml` с тремя независимыми job'ами на `ubuntu-latest`: lint (ruff), typecheck (mypy), test (pytest). Везде `astral-sh/setup-uv@v6` + `uv sync --frozen`; `concurrency: cancel-in-progress` для экономии минут. **На PR #2 все шесть прогонов CI (по три на push и PR) зелёные.**

## Изменённые файлы

```
* pyproject.toml                                    # финализирован
+ uv.lock                                           # сгенерирован uv sync
+ .pre-commit-config.yaml
+ .github/workflows/ci.yml
- .github/workflows/.gitkeep
+ src/shared/__init__.py
+ src/bot/__init__.py
+ src/admin/__init__.py
- src/shared/.gitkeep
- src/bot/.gitkeep
- src/admin/.gitkeep
+ tests/unit/test_smoke.py
* handoff/inbox/TASK-002-tooling.md                 # → in-progress → archive (в отдельном PR)
+ handoff/archive/TASK-002-tooling/task.md          # архивация (этот PR)
+ handoff/outbox/TASK-002-report.md                 # этот отчёт
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen                # установить deps из uv.lock в .venv (uv сама поставит Python 3.12)
uv run pre-commit install       # повесить локальные хуки

# Прогон проверок:
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/shared
uv run pytest
```

CI на GitHub Actions запускается на любой push и на PR в main; результаты в Actions tab. Один прогон lint/typecheck/test ≈ 10–15 секунд после прогрева кеша uv.

## Что не сделано / вынесено

- **Опциональный pytest-хук в pre-commit не подключён.** Замедление коммитов даже на пустом тестсете заметнее, чем у ruff+mypy; CI всё равно ловит регрессии. Если cowork настоит — это однострочный довесок.
- **Build-backend (hatchling) убран целиком.** Заготовка предлагала «hatchling или setuptools», но реально для текущей формы репо ни тот, ни другой не нужны: мы не публикуем wheel и используем `src.*` как namespace package. Когда понадобится Docker-сборка, обычно достаточно `COPY src /app/src` и `python -m src.bot.main` — без build. Если планируется wheel-based deploy — это решение нужно пересмотреть отдельной задачей (вернуть hatchling + `[tool.hatch.build.targets.wheel] packages` — там придётся принять перенаименование импортов либо завести единый top-level пакет).
- **Polished mypy overrides для библиотек без stubs** (`apscheduler`, `passlib` за пределами `types-passlib`, `aiogram`, `factory_boy`, `freezegun`) — не добавлены. На пустом `src/shared` mypy ничего этого не импортирует. Подключим при первой ошибке в реальной задаче (вероятно TASK-005 / модели).
- **Python managed by uv.** В системе нет глобального `python3.12`; uv ставит свой. Для CI это нативно через setup-uv. Для локального запуска вне `uv run` нужно знать про `.venv/bin/python` — в `docs/` это не описано; не вношу правок, оставляю cowork-агенту как кандидата на дополнение `docs/02-tech-stack.md`.

## Открытые вопросы для проектировщика

1. **`[tool.uv] package = false` vs hatchling.** Решение принято внутри задачи, основания — выше. Нужно ли формализовать как ADR-0004 или достаточно записи в `state/DECISIONS.md`?
2. **CI триггеры.** Сейчас `on: push:` без фильтра ветвей + `pull_request: branches: [main]`. CI бежит и на feature-веткивих push'ах, и на сам PR — задвоено. Сужать до `push: branches: [main]` + `pull_request:` сэкономит ~50% минут, но не даст сигнал по feature-ветке до PR. Какой вариант предпочитаешь?
3. **Процесс «cowork-правки сами по себе через отдельный PR».** В рамках TASK-002 пришлось сделать PR #1 для накопившихся правок cowork (state/docs/handoff/pyproject). Это сработало; если процесс закрепляется как штатный — стоит описать его в `handoff/README.md` (одно предложение про «pre-task cleanup PR от исполнителя по правкам cowork»).

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-002: финализирован `pyproject.toml` (верхние границы, `[tool.uv] package=false`), сгенерирован `uv.lock`; pre-commit с локальными хуками через `uv run`; CI на GitHub Actions (lint/typecheck/test, ubuntu-latest, setup-uv@v6); smoke-тест в `tests/unit/`. PR [#2](https://github.com/nmetluk/bettgbot/pull/2) (squash → `bb89808`).
```

## Метрики

- Тестов добавлено: 1 (smoke)
- Коммитов в PR #2: 4 + 1 squash на main
- Runtime зависимостей: 16
- Dev зависимостей: 9
- CI время прогона (cold/warm cache): ~20с / ~10с на job
- Время на выполнение: ~1 час (с учётом отдельного PR #1 для cowork-правок)
