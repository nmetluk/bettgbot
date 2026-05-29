# Brief — analytics

**Дата:** 2026-05-29
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Следующая пост-MVP фича по убыванию пользы/объёма — **«Аналитика и статистика»** (impact «Высокий»,
effort «M» из roadmap-экрана прототипа). Цель из карточки: динамика прогнозов по дням, точность по
категориям, воронка «регистрация → первый прогноз», топ-события.

## Что планировалось

Спроектировать админ-экран `/analytics` и завести задачу исполнителю.

## Что фактически сделано

- Дизайн-решения — в [`decisions.md`](decisions.md).
- Заведена задача [`TASK-059`](../../handoff/inbox/TASK-059-admin-analytics.md).

## Контекст реализации (поля уже есть, миграции не нужны)

Всё считается из существующих таблиц (только чтение):

- `Prediction`: `created_at`, `is_correct (bool|None)`, `user_id`, `event_id`.
- `Event`: `category_id`, `created_at`, `title`, `is_published`, `is_archived`, `result_outcome_id`.
- `Category`: `id`, `name`, `is_active`.
- `User`: `id`, `created_at` (регистрация), `is_blocked`.

Паттерн точности — тот же `func.count().filter(Prediction.is_correct.is_(True))` /
`.isnot(None)`, что в `user_stats`/`leaderboard` (TASK-058).

## Следующие шаги

- После аналитики по ранжиру — «Рассылки и анонсы» (Высокий/M).
- Бот-визуализации/экспорт — вне скоупа этой задачи.
