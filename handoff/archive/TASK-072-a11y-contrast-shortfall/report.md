---
task: TASK-072
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/138
branch: feature/TASK-072-a11y-contrast-shortfall
commits:
  - 6437526 fix(handoff): TASK-072 — increase contrast to WCAG AA thresholds
---

# Отчёт по TASK-072: догнать контраст D1/D3 до WCAG-порогов

## Сводка

Исправлен контраст двух токенов до WCAG-порогов:
- `--pv-blue`: #1B7FB8 → #287EA8 (контраст с белым: 4.40:1 → **4.53:1**, порог ≥4.5:1 ✓)
- `--pv-border`: #b0b0b8 → #8E8E96 (контраст с фоном #fbfbfc: 2.08:1 → **3.14:1**, порог ≥3.0:1 ✓)

Значения подобраны с минимальным отклонением от исходных оттенков.

## Изменённые файлы

```
* src/admin/static/css/tokens.css  # --pv-blue, --pv-border обновлены
+ handoff/archive/TASK-072-a11y-contrast-shortfall/task.md
+ handoff/outbox/TASK-072-report.md
```

## Замеры контраста (WCAG 2.x relative luminance)

| Токен | Было | Стало | Фон | Контраст | Порог | Статус |
|-------|------|-------|-----|----------|-------|--------|
| --pv-blue | #1B7FB8 (4.40:1) | **#287EA8** | #FFFFFF | **4.53:1** | ≥4.5:1 (AA) | ✓ |
| --pv-border | #b0b0b8 (2.08:1) | **#8E8E96** | #FBFBFC | **3.14:1** | ≥3.0:1 (1.4.11) | ✓ |

## Как воспроизвести / запустить

```bash
# визуальная проверка — открыть админку, проверить кнопки/бордеры
make admin

# тесты
uv run ruff check . && uv run mypy src/shared && uv run pytest tests/unit -q
```

## Что не сделано

Ничего — все требования задачи выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-072: исправлен контраст primary/border до WCAG AA (PR #138)
```
