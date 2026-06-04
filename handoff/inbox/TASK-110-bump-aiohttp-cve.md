---
id: TASK-110
created: 2026-06-04
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - .github/workflows/ci.yml
priority: high
estimate: S
---

# TASK-110: Бамп aiohttp ≥3.14.0 (2 CVE) — чинит красный pip-audit на main

## Контекст

После полуночи UTC 2026-06-04 на `main` покраснел CI — **только** job `Security (Dependencies - pip-audit)` (остальное зелёное: lint/mypy/unit/integration). `pip-audit --strict` — hard-gate; опубликованы свежие advisory:

```
aiohttp 3.13.5  CVE-2026-34993  → fix 3.14.0
aiohttp 3.13.5  CVE-2026-47265  → fix 3.14.0
```

`aiohttp` — транзитивная зависимость (через `aiogram`, ограничение `<4`, так что `3.14.0` допустимо). Код приложения ни при чём; чинится бампом зависимости + перегенерацией lock. **Блокирует все будущие auto-merge** (required-чек красный), поэтому срочно.

## Цель

`aiohttp` в `uv.lock` поднят до ≥3.14.0, `pip-audit --strict` снова зелёный.

## Definition of Done

- [ ] `uv lock --upgrade-package aiohttp` (поднимет до 3.14.0 в рамках `aiogram`-ограничения). Если резолвер потянет смежные пакеты — проверить, что ничего не сломалось.
- [ ] (Опц.) если хочется явный пол — добавить `aiohttp>=3.14.0` в `pyproject.toml` `dependencies` и `uv lock`. Но достаточно и `--upgrade-package`.
- [ ] Проверка локально: `uv sync --frozen && uv pip freeze > /tmp/r.txt && uv run pip-audit --strict --requirement /tmp/r.txt` → **No known vulnerabilities** (или хотя бы без aiohttp CVE).
- [ ] `uv run pytest` зелёный (убедиться, что 3.14.0 не сломал aiogram/рантайм), `ruff`/`mypy` зелёные.
- [ ] PR `TASK-110: bump aiohttp to fix CVE-2026-34993/47265`; отчёт; move inbox→archive; rebase на свежий main; явный `gh pr merge --auto --squash`.

## Подсказки / границы
- Менять только `uv.lock` (+ опц. pyproject-constraint). Не апгрейдить всё подряд — таргетно `aiohttp`.
- Если позже всплывут новые CVE в других пакетах (advisory публикуются ежедневно) — это отдельные бампы; здесь только aiohttp.
- Альтернатива «заигнорить CVE через `--ignore-vuln`» — **не использовать**: фикс (3.14.0) доступен, игнор скрыл бы реальную дыру.

## Ссылки
- pip-audit job: `.github/workflows/ci.yml` (`security-deps`)
- Красный ран: CI #717 на main (commit v0.2.1)
