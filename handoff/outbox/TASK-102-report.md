---
task: TASK-102
completed: 2026-06-03
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/232
commits:
  - 4d050e2 TASK-102: audit and fix date-dependent test time-bombs
---

# Отчёт по TASK-102: аудит и устранение date-зависимых тестов

> ⚠️ Отчёт оформлен cowork-агентом post-factum: код влит (PR #232), но исполнитель не написал отчёт и не заархивировал задачу. Cowork восстановил handoff-гигиену (этот отчёт + перенос inbox→archive) и сверил факт по `origin/main`.

## Сводка

Устранены «тайм-бомбы» — тесты, чьё прохождение зависело от разрыва между фиксированной датой в данных и реальным `utcnow()` в коде (после первого инцидента в `test_prediction_analytics`, исправленного в PR #207).

Выбран **предпочтительный путь из задачи** — инъекция опорного момента времени (`reference_now`) в методы repo/service со скользящими окнами, дефолт `utcnow()`; в тестах передаётся фиксированный момент → полный детерминизм без зависимости от реального календаря.

## Изменённые файлы (по diff #232)

```
* src/shared/services/stats.py            # reference_now в оконных методах
* src/shared/services/dashboard.py
* src/shared/repositories/prediction.py
* src/shared/repositories/user.py
* src/bot/scheduler/jobs.py               # проброс reference_now где нужно
* tests/integration/repositories/test_prediction_analytics.py
* tests/integration/services/test_stats_service.py
* tests/unit/bot/scheduler/test_admin_digest.py
```

## Проверка (cowork)

- CI PR #232 зелёный (lint/typecheck/unit/integration/handoff-consistency) → mypy/тесты прошли.
- Существующие вызовы не сломаны: `reference_now` опционален с дефолтом `utcnow()`.

## Открытые вопросы

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-06-03 — TASK-102: устранены date-зависимые «тайм-бомбы» в тестах через инъекцию `reference_now` (дефолт `utcnow()`), детерминизм без реального времени (PR #232).
```
