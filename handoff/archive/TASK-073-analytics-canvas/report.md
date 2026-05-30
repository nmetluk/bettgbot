---
task: TASK-073
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/143
branch: feature/TASK-073-analytics-canvas
commits:
  - a4eb067 feat(admin): analytics canvas sizing + empty state
---

# Отчёт по TASK-073: график аналитики — размеры canvas и пустое состояние

## Сводка

Приведён график на `/analytics` к аккуратному виду:
- Canvas растянут на ширину карточки (`width: 100%`), высота задана через CSS токены
- Добавлены токены `--pv-chart-h-sm: 250px`, `--pv-chart-h-md: 300px`
- Инлайн высоты заменены на CSS классы `.pv-chart` / `.pv-chart-sm`
- Добавлен класс `.pv-empty-state` с центрированным текстом и иконкой (через `data-icon`)
- Добавлено пустое состояние для графика динамики при отсутствии данных

## Изменённые файлы

```
* src/admin/static/css/tokens.css  -- новые токены --pv-chart-h-*
* src/admin/static/css/app.css     -- .pv-chart, .pv-empty-state классы
* src/admin/templates/analytics/list.html  -- использование классов, пустое состояние
```

## Как воспроизвести / запустить

```bash
# Визуальная проверка: открыть /analytics
make admin
# Проверить с данными и без (пустая БД или период без прогнозов)
```

## Что не сделано

Ничего — все требования задачи выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-073: исправлены размеры canvas и пустое состояние аналитики (PR #143)
```
