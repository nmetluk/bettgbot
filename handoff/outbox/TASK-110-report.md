---
task: TASK-110
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/240
branch: feature/TASK-110-bump-aiohttp-cve
commits:
  - 7c8d130 chore(deps): bump aiohttp to 3.14.0 via uv override to fix CVE-2026-34993/47265 (TASK-110)
---

# Отчёт по TASK-110: Бамп aiohttp ≥3.14.0 (2 CVE) — чинит красный pip-audit на main

## Сводка

Выполнена задача по устранению красного CI (job Security (Dependencies - pip-audit) на main после публикации CVE-2026-34993 и CVE-2026-47265 в aiohttp 3.13.5.

Поскольку `aiogram` (3.28.2) в своих метаданных декларирует `aiohttp<3.14,>=3.9.0`, прямой `uv lock --upgrade-package aiohttp` без дополнительных мер не поднимал версию (резолвер uv соблюдает upper bound транзитивной зависимости). 

Решение: добавлен `override-dependencies` в `[tool.uv]` — это официальный механизм uv для форсирования версии транзитивной зависимости, игнорируя конфликтующие bounds от других пакетов (aiogram). В lock и в `.venv` после `uv sync` теперь aiohttp 3.14.0.

Параллельно обновлён CI (`security-deps` job): переход с `uv pip freeze > reqs && uv run pip-audit --strict --requirement reqs` на прямой `uv run pip-audit --strict`. Причина: `--requirement` внутри pip-audit создаёт temp-venv и запускает обычный `pip install -r`, который видит конфликт метаданных aiogram + aiohttp 3.14 и падает с ResolutionImpossible. Прямой запуск на уже заsync'енной uv-среде видит установленный 3.14.0 (override применён uv'ом) и успешно проходит аудит.

Все проверки зелёные. Никаких других пакетов не задето.

## Изменённые файлы

```
* pyproject.toml            # + [tool.uv] override-dependencies = ["aiohttp>=3.14.0,<4"]
* uv.lock                   # aiohttp 3.13.5 → 3.14.0 (только это изменение по пакетам)
* .github/workflows/ci.yml  # security-deps: прямой pip-audit (комментарий с объяснением)
```

## Как воспроизвести / запустить

```bash
# после чекаута ветки / main после merge
uv sync --frozen

# проверка аудита (как теперь в CI и локально)
uv run pip-audit --strict
# → No known vulnerabilities found

# полный DoD-прогон (как требуется CLAUDE.md)
uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src/shared && uv run pytest -q
```

Команда из задачи с `--requirement /tmp/r.txt` теперь не работает (plain-pip conflict), вместо неё — прямой запуск на env (эквивалентно по сути, т.к. uv уже зарезолвил и установил 3.14.0).

## Что не сделано (если применимо)

- Не добавлял `aiohttp>=3.14.0` в `[project.dependencies]` (это вызвало бы unsatisfiable при резолве без override; override — более точный инструмент для именно этой ситуации).
- Не игнорил CVE через `--ignore-vuln` (как и требовалось в задаче).
- Не менял docs/state (не требуется).

## Открытые вопросы для проектировщика

- В будущем, когда aiogram выпустит версию с aiohttp>=3.14 в своих requires, override можно будет убрать (но пока — необходим).
- Возможно, стоит задокументировать паттерн "uv override для CVE транзитивок" в docs/02-tech-stack.md или DECISIONS (на усмотрение).

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-06-04 — **TASK-110 закрыт:** aiohttp bumped to 3.14.0 (CVE-2026-34993/47265) через `[tool.uv] override-dependencies` + фикс invocation pip-audit в CI (PR #240).
```

## Метрики (опционально)

- Тестов добавлено: 0 (только deps + infra CI)
- Время на выполнение: ~25 мин (вкл. эксперименты с резолвом/аудитом + отчёт).
- CI: ожидается зелёный после прогона на PR (auto-merge включён).
