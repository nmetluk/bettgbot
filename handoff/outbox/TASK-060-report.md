---
task: TASK-060
title: Графики аналитики через внешний JS — CSP-совместимо
status: completed
date: 2026-05-29
---

# Отчёт по TASK-060

## Что сделано

Исправлен CSP-регресс TASK-059: инлайн-скрипт инициализации Chart.js блокируется строгим CSP.
Инлайн-код вынесен во внешний JS-файл, данные передаются через JSON-блок.

### Реализация

**`src/admin/static/js/analytics.js` (новый)**
- IIFE-модуль, читает данные из `<script type="application/json" id="analytics-data">`
- `getAnalyticsData()` — парсит JSON из блока данных
- `initDailyChart()` — строит line-график динамики по дням
- `initCategoryChart()` — строит bar-график точности по категориям
- `initCharts()` — точка входа на DOMContentLoaded
- Гард: проверяет наличие `Chart` глобального объекта, пустых данных, canvas-элементов

**`src/admin/templates/analytics/list.html`**
- Удалён инлайн-`<script>` с вызовами `new Chart(...)`
- Добавлен `<script type="application/json" id="analytics-data">` с данными (`daily_counts`, `category_accuracy`)
- Добавлен `<script src="/static/js/analytics.js" defer>` после Chart.js CDN

**`tests/unit/admin/test_analytics_handler.py`**
- Обновлён `test_analytics_renders_chart_script`:
  - Проверяет наличие `/static/js/analytics.js`
  - Проверяет наличие JSON-блока с `id="analytics-data"` и `type="application/json"`
  - Проверяет ключи `"daily_counts"` и `"category_accuracy"` в данных
  - Проверяет canvas-элементы `dailyChart` и `categoryChart`

### CSP

CSP-заголовок (`src/admin/_security_headers.py`) **не менялся**: `script-src 'self' https://cdn.jsdelivr.net`.
Паттерн `<script type="application/json">` — это данные, не исполняемый код, поэтому CSP `script-src`
его не контролирует (в отличие от `<script>` без `type` или с `type="text/javascript"`).

## Что не сделано

Браузерная проверка не выполнена (нет доступа к devtools консоли). Владелец должен проверить:
1. Открыть `/analytics`, devtools-консоль — ноль CSP-violation'ов
2. Оба графика отрисовываются с данными
3. Состояние «данных нет» не падает

## Коммиты

- `fix(admin): CSP-compliant analytics charts (TASK-060)` — 7d6df2b
- Merge commit на main: 5d14be9

## PR

https://github.com/nmetluk/bettgbot/pull/118 (слит)

## Воспроизведение локально

```bash
# Запуск админки
make admin
# или
uv run uvicorn src.admin.app:app --reload

# Переход на экран
http://localhost:8000/analytics

# Проверить в devtools-консоли:
# - Нет ошибок CSP (Refused to execute inline script)
# - Нет ошибок JS (Chart is not defined, analytics-data not found)
# - Графики отрисовываются
```

```bash
# Тесты
uv run pytest tests/unit/admin/test_analytics_handler.py -v

# Проверка на инлайн-скрипты
git grep -n '<script>' src/admin/templates/
# Должно быть пусто (или только <script src= ... > с внешними файлами)
```

## Diff-сводка

- `src/admin/static/js/analytics.js` +153 строки (новый файл)
- `src/admin/templates/analytics/list.html` -76 строк (инлайн удалён, +14 для JSON/external script)
- `tests/unit/admin/test_analytics_handler.py` +12/-7 строк (обновлён тест)
