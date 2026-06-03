---
id: TASK-102
created: 2026-06-03
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - tests/integration/repositories/test_prediction_analytics.py
priority: normal
estimate: S
---

# TASK-102: Аудит и устранение date-зависимых («тайм-бомба») тестов

## Контекст

2026-06-03 интеграционный CI внезапно покраснел на `test_prediction_analytics.py::test_daily_prediction_counts_30_day_window`, **блокируя все PR**. Причина — тест анкорил данные к фиксированной дате (`now = 2026-05-29`), а репозиторий/сервис (`PredictionRepository.daily_prediction_counts` / `StatsService`) считают скользящее окно от реального `utcnow()`. После полуночи UTC 2026-06-03 прогноз «-25 дней» (2026-05-04) выпал из 30-дневного окна → `assert 28 == 27`. Точечно уже починено (фикстура `now` → реальное `datetime.now(tz=UTC)`, в составе PR #207). Нужно проверить, нет ли таких же мин в других тестах.

## Цель

Найти и обезвредить все тесты, чьё прохождение зависит от **разрыва между фиксированной датой в данных и реальным `utcnow()`** в коде, чтобы CI не падал «по календарю».

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-102-report.md`.

- [ ] Прогон-аудит: найти тесты с фиксированными датами/`datetime(YYYY, M, D...)`/жёстко заданными `now`, которые сравниваются с кодом на `utcnow()`-окнах. Кандидаты в первую очередь: `tests/integration/repositories/test_prediction_analytics.py` (другие тесты файла), `test_leaderboard_period_filter` (в `test_stats_service.py`/repo), всё, что зовёт `daily_prediction_counts`, `leaderboard(period=...)`, `count_24h`, `count_active_*`, reminder-окна.
  - Греп-старт: `grep -rn "datetime(20" tests/` и `grep -rn "now =" tests/`.
- [ ] Для каждого найденного: либо привязать данные к реальному `datetime.now(tz=UTC)` (как в фиксе #207), либо — предпочтительно — сделать окно в коде инъектируемым (передавать `reference_now` параметром в repo/service-метод, дефолт `utcnow()`), и в тесте передавать фиксированный момент. Второй путь даёт полный детерминизм без «реального времени» в тестах — **на твоё усмотрение**, но единообразно; решение зафиксируй в отчёте.
- [ ] Прогон `uv run pytest`, `ruff check`, `ruff format --check src tests`, `mypy src/shared` — зелёные.
- [ ] PR `TASK-102: kill date-dependent test time-bombs`; отчёт; move inbox→archive; ветка отребейзена на свежий `main` перед PR; `gh pr merge --auto --squash`.

## Подсказки / границы

- Не менять поведение продакшн-кода ради теста без необходимости; если вводишь `reference_now`-параметр — он опционален с дефолтом `utcnow()`, существующие вызовы не ломаются.
- Не трогать `docs/`/`state/` — зона cowork.
- Это гигиена тестов, не фича: бизнес-логика окон остаётся прежней.

## Ссылки

- Прецедент и фикс: PR #207 (фикстура `now` в `test_prediction_analytics.py`)
- Окна в коде: `src/shared/repositories/prediction.py` (`daily_prediction_counts`, `leaderboard`, `count_24h`), `src/shared/services/stats.py`
