---
task: TASK-059
title: Экран «Аналитика и статистика» в админке
status: completed
date: 2026-05-29
---

# Отчёт по TASK-059

## Что сделано

Реализован экран `/analytics` с четырьмя метриками согласно DoD:

### Данные (репозиторий/сервис)

**`src/shared/repositories/prediction.py`**
- `daily_prediction_counts(days=30)` — группировка прогнозов по дням за 30 дней
- `category_accuracy()` — точность по категориям (JOIN Prediction→Event→Category, `correct/resolved*100`)
- `funnel_metrics()` — воронка «регистрация → первый прогноз» (всего незаблокированных vs сделавших прогноз)
- `top_events(limit=10)` — топ событий по числу прогнозов с title и категорией

**`src/shared/services/stats.py`**
- Dataclass'ы: `AnalyticsDayRow`, `CategoryAccuracyRow`, `AnalyticsFunnelMetrics`, `AnalyticsTopEventRow`
- Методы сервиса для всех четырёх метрик (преобразуют кортежи репозитория в типизированные структуры)
- `daily_prediction_counts` заполняет нулевые дни для ровного ряда графика

### Экран

**`src/admin/routes/analytics.py`**
- GET `/analytics` под `current_admin`
- Вызывает все 4 метода сервиса, передаёт данные в шаблон

**`src/admin/templates/analytics/list.html`**
- График динамики по дням: line chart через Chart.js (фиолетовый)
- График точности по категориям: bar chart через Chart.js
- Таблица точности с бейджами (success/warning/secondary)
- KPI воронки: 3 карточки (всего пользователей, сделали прогноз, конверсия %)
- Таблица топ-10 событий с кликом на карточку события
- Пустые состояния для всех секций
- Chart.js 4.4.2 через CDN (CSP-совместимый, script-src разрешает jsdelivr)

**Навигация**
- Пункт «Аналитика» в sidebar с иконкой `monitoring` (раздел «Управление»)

### Качество

**`tests/integration/repositories/test_prediction_analytics.py`**
- `test_daily_prediction_counts_30_day_window` — проверка окна и заполнения нулей сервисом
- `test_category_accuracy_calculation` — проверка формулы `correct/resolved*100`, исключение категорий без разрешённых
- `test_funnel_metrics` — проверка воронки (total vs with_pred, исключение заблокированных)
- `test_top_events_by_prediction_count` — проверка сортировки по count

**`tests/unit/admin/test_analytics_handler.py`**
- `test_analytics_renders_all_sections` — проверка вызова всех 4 методов сервиса и рендера KPI/категорий/событий
- `test_analytics_empty_category_accuracy` — проверка пустого состояния
- `test_analytics_renders_chart_script` — проверка наличия Chart.js и данных графиков

**CI**
- Все проверки зелёные: ruff, mypy strict, pytest (unit + integration), security checks

## Что не сделано

Ничего — все пункты DoD выполнены.

## Коммиты

- `feat(admin): analytics screen with 4 metrics (TASK-059)` — 17c22a5
- `style(tests): ruff format on test_prediction_analytics` — 2866a29
- Merge commit на main: 46bf676

## PR

https://github.com/nmetluk/bettgbot/pull/117 (слит)

## Воспроизведение локально

```bash
# Запуск админки
make admin
# или
uv run uvicorn src.admin.app:app --reload

# Переход на экран
http://localhost:8000/analytics
```

```bash
# Тесты
uv run pytest tests/unit/admin/test_analytics_handler.py -v
uv run pytest tests/integration/repositories/test_prediction_analytics.py -v

# Линт/типы
uv run ruff check src/admin/routes/analytics.py
uv run mypy src/shared/repositories/prediction.py src/shared/services/stats.py --strict
```

## Diff-сводка

- `src/shared/repositories/prediction.py` +115 строк (4 метода агрегации)
- `src/shared/services/stats.py` +106 строк (методы + dataclass'ы)
- `src/admin/routes/analytics.py` +54 строки (новый роут)
- `src/admin/templates/analytics/list.html` +207 строк (шаблон с графиками)
- `src/admin/templates/_layout_shell.html` +4 строки (навигация)
- `src/admin/app.py` +2 строки (регистрация роута)
- `tests/integration/repositories/test_prediction_analytics.py` +283 строки
- `tests/unit/admin/test_analytics_handler.py` +194 строки
