---
id: TASK-059
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - sessions/2026-05-29-03-analytics/decisions.md
  - src/shared/services/stats.py
  - src/shared/repositories/prediction.py
priority: normal
estimate: M
---

# TASK-059: Экран «Аналитика и статистика» в админке

## Контекст

Следующая пост-MVP фича по убыванию пользы/объёма (Высокий/M из roadmap-экрана прототипа).
Дизайн-решения — в [`sessions/2026-05-29-03-analytics/decisions.md`](../../sessions/2026-05-29-03-analytics/decisions.md).

Всё считается **только чтением** из существующих таблиц — новой модели и миграции **не нужно**.
Паттерн точности — тот же `func.count().filter(Prediction.is_correct.is_(True))` / `.isnot(None)`,
что в `user_stats`/`leaderboard` (TASK-058).

## Цель

Админ-экран `/analytics` с четырьмя метриками: динамика прогнозов по дням, точность по категориям,
воронка «регистрация → первый прогноз», топ-события.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-059-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).

**Данные (репозиторий/сервис):**

- [ ] Динамика по дням: счётчик прогнозов `GROUP BY date(created_at)` за последние 30 дней; дни без прогнозов заполнены нулями (ровный ряд для графика).
- [ ] Точность по категориям: JOIN Prediction→Event→Category, `correct = count(is_correct is True)`, `resolved = count(is_correct is not None)`, `accuracy = correct/resolved*100` (через `cast(...NUMERIC)`, без целочисленного деления), сгруппировано по категории; категории без разрешённых прогнозов показывать с пометкой «нет данных» либо исключать (на выбор, отразить в отчёте).
- [ ] Воронка: `всего незаблокированных пользователей`, `сделавших ≥1 прогноз (distinct user_id)`, конверсия `%`.
- [ ] Топ-события: `count(Prediction) GROUP BY event_id ORDER BY desc LIMIT 10`, JOIN Event для `title` и категории.
- [ ] Агрегаты живут в `StatsService` (+ методы в `PredictionRepository`/новых при необходимости), типизированные dataclass'ы; роут без бизнес-логики.

**Экран:**

- [ ] `GET /analytics` (`src/admin/routes/`, зарегистрировать в `app.py`), под `current_admin`.
- [ ] Шаблон `src/admin/templates/analytics/list.html` (extends `base.html`, на дизайн-системе v2: `.pv-card`/`.pv-table`/`.pv-kpi`).
- [ ] Графики через **Chart.js** с `https://cdn.jsdelivr.net` (canvas, без `eval` — текущий CSP уже разрешает jsdelivr в `script-src`, менять CSP не нужно; проверить, что страница не падает на CSP): динамика по дням — line, точность по категориям — bar. Воронка и топ-события — таблицы/CSS-бары.
- [ ] Пункт «Аналитика» в навигации `base.html` (раздел «Журнал» или «Управление»), иконка из прототипа — `monitoring`.
- [ ] Пустые состояния, когда данных нет (новый проект без прогнозов) — без падений и пустого графика.

**Качество:**

- [ ] Integration-тесты на каждый агрегат (фикстуры с прогнозами в разных категориях/датах/`is_correct`; проверка дневной группировки, точности, воронки, топа). Unit на хэндлер (200, рендер секций, пустое состояние).
- [ ] `uv run pytest` зелёный полностью; `ruff`/`mypy` чисто; PR `TASK-059: ...`; CI зелёный; смёрджено.
- [ ] Отчёт + archive директорией (`handoff/archive/TASK-059-admin-analytics/task.md`). Меняешь текст шаблона — синхронно правь текстовые ассерты тестов.

## Вне скоупа

- Экспорт CSV/PDF, визуализации в боте, произвольный диапазон дат (только фикс. окно 30 дней + all-time там, где уместно) — отдельные будущие задачи.

## Артефакты

- `* src/shared/repositories/prediction.py` (+ возможно `event.py`) — агрегаты
- `* src/shared/services/stats.py` — методы аналитики + dataclass'ы
- `+ src/admin/routes/analytics.py`; `* src/admin/app.py` — регистрация
- `+ src/admin/templates/analytics/list.html`; `* base.html` — навигация
- `+ tests/...` — integration + unit

## Ссылки

- Дизайн: [`sessions/2026-05-29-03-analytics/decisions.md`](../../sessions/2026-05-29-03-analytics/decisions.md)
- Паттерн агрегации: `PredictionRepository.leaderboard()`/`user_stats()` в [`src/shared/repositories/prediction.py`](../../src/shared/repositories/prediction.py)
- CSP: [`src/admin/_security_headers.py`](../../src/admin/_security_headers.py) (script-src уже разрешает jsdelivr)
- Визуальный эталон стиля — `sessions/2026-05-29-01-admin-design/artifacts/admin/` (карточки/таблицы)

## Подсказки исполнителю

- Дневную группировку делай в SQL (`func.date(...)` / `date_trunc('day', ...)`), а заполнение нулевых дней — в Python по диапазону, чтобы график не имел разрывов.
- Chart.js: проверь в браузере devtools-консоль на CSP-ошибки после подключения (как договорились в TASK-057). Если Chart.js потребует чего-то сверх текущего CSP — это **открытый вопрос**, оформи `outbox/TASK-059-question.md`, не ослабляй CSP молча.
- Деление на ноль в точности/воронке — гард на `resolved == 0` / `users == 0` (показывать 0.0% или «нет данных»).
