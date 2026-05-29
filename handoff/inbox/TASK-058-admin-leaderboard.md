---
id: TASK-058
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: ["TASK-057"]
related:
  - src/shared/services/stats.py
  - src/shared/repositories/prediction.py
  - sessions/2026-05-29-02-leaderboard/decisions.md
priority: normal
estimate: M
---

# TASK-058: Лидерборд пользователей в админке

## Контекст

Первая пост-MVP фича, выбранная по убыванию пользы/объёма из roadmap-экрана прототипа: **рейтинг
пользователей** (impact «Высокий», effort «S», данные уже в `Prediction.is_correct`). Главный
геймификационный крючок — рейтинг по точности прогнозов.

Дизайн-решения — в [`sessions/2026-05-29-02-leaderboard/decisions.md`](../../sessions/2026-05-29-02-leaderboard/decisions.md).
Идёт **после** TASK-057 (прод-готовность v2), поэтому `blockedBy: [TASK-057]`.

В коде уже есть всё нужное: `Prediction.is_correct: bool | None` (None = не разрешён, True/False —
после фиксации итога), паттерн агрегации в `PredictionRepository.user_stats()`
(`func.count().filter(Prediction.is_correct.is_(True))` и `.isnot(None)`), сервис `StatsService`.

## Цель

Админ-экран `/leaderboard` с рейтингом пользователей по точности прогнозов.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-058-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).

- [ ] `PredictionRepository.leaderboard(*, min_resolved: int = 5, limit: int = 100, period: <см. ниже>)` — **один** SQL: `GROUP BY user_id`, `count(is_correct is True)` как `correct`, `count(is_correct is not None)` как `resolved`, `HAVING resolved >= min_resolved`, JOIN `User` для отображаемого имени/username, сортировка по точности ↓, затем `correct` ↓, затем `resolved` ↓. Без N+1.
- [ ] Метрика: `accuracy = round(correct / resolved * 100, 1)`. Пользователи с `resolved < min_resolved` в рейтинг не попадают.
- [ ] `StatsService.leaderboard(...)` — обёртка над репозиторием, возвращает типизированный список (dataclass `LeaderboardRow`: rank, user_id, display_name, correct, resolved, accuracy).
- [ ] Период: **all-time обязательно**; фильтр `period in {all, 30d, 90d}` — опционально (по `Prediction.created_at`), если делаешь — отрази в UI селектором.
- [ ] Роут `GET /leaderboard` (`src/admin/routes/`, зарегистрировать в app): без бизнес-логики, только вызов сервиса + рендер. Доступ под `current_admin`, как остальные экраны.
- [ ] Шаблон `src/admin/templates/leaderboard/list.html` на v2: extends `base.html`, таблица на `.pv-table` (колонки: Место, Пользователь, Точность, Верных, Разрешено), топ-3 выделить (медаль/бейдж). Пустое состояние, если никто не прошёл порог.
- [ ] Пункт «Рейтинг» в навигации `base.html` (раздел «Управление» или «Развитие»), иконка из набора Material Symbols (в прототипе — `leaderboard`).
- [ ] Тесты: integration на агрегацию (`leaderboard()` — корректность порога, сортировки, точности на фикстурах с разными is_correct) + unit на хэндлер (200, рендер строк, пустое состояние).
- [ ] `uv run pytest` зелёный полностью; `ruff`/`mypy` чисто; PR `TASK-058: ...`; CI зелёный; смёрджено.
- [ ] Отчёт + archive директорией (`handoff/archive/TASK-058-admin-leaderboard/task.md`). Меняешь текст шаблона — синхронно правь текстовые ассерты тестов.

## Вне скоупа

- Бот-команда `/leaderboard` — отдельная будущая задача (здесь только админ-экран).
- Анти-чит/исключение заблокированных: по умолчанию `is_blocked` пользователи **исключаются** из рейтинга (добавить в `WHERE`).

## Артефакты

- `* src/shared/repositories/prediction.py` — метод `leaderboard()`
- `* src/shared/services/stats.py` — `leaderboard()` + dataclass `LeaderboardRow`
- `+ src/admin/routes/leaderboard.py` — роут
- `* src/admin/app.py` — регистрация роутера
- `+ src/admin/templates/leaderboard/list.html`
- `* src/admin/templates/base.html` — пункт навигации «Рейтинг»
- `+ tests/...` — integration + unit

## Ссылки

- Дизайн: [`sessions/2026-05-29-02-leaderboard/decisions.md`](../../sessions/2026-05-29-02-leaderboard/decisions.md)
- Паттерн агрегации: `PredictionRepository.user_stats()` в [`src/shared/repositories/prediction.py`](../../src/shared/repositories/prediction.py)
- Визуальный эталон: `sessions/2026-05-29-01-admin-design/artifacts/admin/page-roadmap.jsx` (карточка «Рейтинг пользователей»), общий стиль — `page-users.jsx`

## Подсказки исполнителю

- Точность считать в SQL или в Python из `(correct, resolved)` — на твоё усмотрение, но сортировку по точности делай в SQL, чтобы `limit` отсекал правильных.
- Деление на ноль: порог `HAVING resolved >= min_resolved` (min_resolved ≥ 1) уже гарантирует `resolved > 0`.
