---
task: TASK-102
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/232
branch: feature/TASK-102-audit-date-dependent-tests
commits:
  - 628cfde test: audit and fix date-dependent tests by injecting reference_now (TASK-102)
---
# Отчёт по TASK-102: Аудит и устранение date-зависимых («тайм-бомба») тестов

## Сводка

Выполнен полный аудит и устранение тайм-бомб в тестах, чьё прохождение зависело от разрыва между фиксированными датами в сидах и реальным `utcnow()` в оконных запросах репозиториев/сервисов (daily/30d/24h/leaderboard period). Это блокировало CI для всех предыдущих PR (в т.ч. 107/103/104/108).

- Сделан греп-аудит (`datetime(20`, `now =`, вызовы `daily_prediction_counts|leaderboard.*period|count_24h|count_active`).
- Введён опциональный параметр `reference_now: datetime | None = None` (дефолт — `utcnow()`) в:
  - `PredictionRepository.daily_prediction_counts`, `count_24h` (с делегацией в существующий `count_predictions_since`), `leaderboard(period_days=...)`
  - `UserRepository.count_active_30d` (с делегацией в `count_active_since`)
  - `StatsService.daily_prediction_counts`, `leaderboard`, `daily_admin_digest` (TASK-098 обогащение)
  - `DashboardService.get_counters` (для 24h/30d счётчиков)
- Прод-вызовы (роуты админки, scheduler jobs) оставлены без явного `reference_now` — используют реальное время (как и раньше).
- Тесты стабилизированы: `test_prediction_analytics.py` — фикстура `now` теперь возвращает фиксированную `2026-06-03` (вместо `datetime.now`), все вызовы передают `reference_now=now`; `test_stats_service.py::test_leaderboard_period_filter` обёрнут в `freeze_time` + передача ref; `test_admin_digest.py` обновлён под текущий дизайн (StatsService) + assert на `reference_now`.
- Обновлены mock-ассерты в unit-тестах хендлеров (analytics/leaderboard) — без `reference_now` (роуты не форвардят его).
- Rebase на свежий main (с 098/107+), разрешены конфликты (сохранены helper'ы `count_*_since` + добавлена ref-логика).
- Полный DoD-прогон (ruff check + format --check, mypy src/shared, pytest) — зелёный. Убраны последние 2+ фейла в analytics/period (которые падали 2026-06-03+).

Решение по инъекции (предпочтительный вариант по задаче) даёт полный детерминизм в тестах без "реального времени" и без изменения прод-поведения. Единообразно применено ко всем оконным методам, затронутым в аудите.

## Изменённые файлы

```
* src/shared/repositories/prediction.py       # +reference_now в daily/leaderboard/count_24h (+интеграция с helper'ами)
* src/shared/repositories/user.py             # +reference_now в count_active_30d (+делегация)
* src/shared/services/stats.py                # +reference_now в daily/leaderboard/daily_admin_digest; обновлены внутренние cutoffs
* src/shared/services/dashboard.py            # +reference_now в get_counters (проброс в 24h/30d)
* src/bot/scheduler/jobs.py                   # daily_admin_digest(reference_now=now) в digest-джобе
* tests/integration/repositories/test_prediction_analytics.py  # fixed now-fixture 2026-06-03, reference_now= в вызовах
* tests/integration/services/test_stats_service.py  # freeze + ref в period_filter; обновлены вызовы count_24h
* tests/unit/admin/test_analytics_handler.py    # mock assert без ref (соответствует вызову из роута)
* tests/unit/admin/test_leaderboard_handler.py  # аналогично, 3 ассерта
* tests/unit/bot/scheduler/test_admin_digest.py # обновлён под StatsService + assert reference_now
+ handoff/outbox/TASK-102-report.md
```

(Также incidental reformat 2 файлов ruff'ом.)

## Как воспроизвести / запустить

```bash
# 1. Переключиться на ветку (после fetch)
git checkout feature/TASK-102-audit-date-dependent-tests
git pull --ff-only origin feature/TASK-102-audit-date-dependent-tests

# 2. Аудит (как в DoD задачи)
grep -rn "datetime(20" tests/ --include="*.py"
grep -rn "now =" tests/ --include="*.py"
grep -rn "daily_prediction_counts\|leaderboard.*period_days\|count_24h\|count_active" tests/ --include="*.py" | grep -E "(assert|call)"

# 3. Полный DoD (обязательно с format --check)
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/shared
uv run pytest -q --tb=no

# 4. Точечно критичные (были тайм-бомбы)
uv run pytest tests/integration/repositories/test_prediction_analytics.py -q --tb=line
uv run pytest tests/integration/services/test_stats_service.py::test_leaderboard_period_filter -q --tb=line
uv run pytest tests/unit/bot/scheduler/test_admin_digest.py -q --tb=line
```

## Что не сделано (если применимо)

- Не добавлял reference_now во все возможные методы (например, reminder.find_candidates уже принимал явный `now`, event archive stale и т.п. — не падали по той же причине; не трогал без необходимости).
- Не менял docs/ (в т.ч. 07-deployment), state/, README, конвенции — зона cowork.
- Не добавлял новые тесты поверх (гигиена, не фича); использовал существующие + минимальные правки.
- uv.lock не коммитил (только version bump от других, не наш).
- Не пушил handoff-маркеры (.in-progress) в feature-коммит.

## Открытые вопросы для проектировщика

- Нет. Всё в скоупе закрыто, тесты теперь герметичны независимо от календаря запуска CI.
- (Опционально) Можно рассмотреть добавление reference_now в другие оконные штуки (напр. top_events_in_window и т.п. из 098), если они будут юзаться в датах-тестах позже — но на сейчас не требуется.

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-102: аудит и устранение date-зависимых тестов (инъекция reference_now в Prediction/User/Stats/Dashboard + стабилизация analytics/period/digest тестов через freeze/fixed now). Блокировка CI для 107/103/104/108 снята. (PR #232)

## Метрики (опционально)

- Затронуто ~10 файлов (в основном тесты + узкие места в repo/service).
- 0 фейлов в pytest после; все гейты зелёные локально.
- Время: ~2-3 итерации на диагностику + фиксы + rebase.
