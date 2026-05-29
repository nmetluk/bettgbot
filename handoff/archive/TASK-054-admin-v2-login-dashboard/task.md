---
id: TASK-054
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: ["TASK-053"]
related:
  - docs/adr/0005-admin-v2-stack.md
  - sessions/2026-05-29-01-admin-design/artifacts/admin/
priority: normal
estimate: M
---

# TASK-054: Переверстать экран входа и дашборд в дизайн v2

## Контекст

После фундамента дизайн-системы (TASK-053) поэкранно переводим существующую админку на визуальный
язык прототипа v2. Эта задача — экран входа (`page-login.jsx`) и дашборд (`page-dashboard.jsx`).
Счётчики дашборда уже реализованы (TASK-043/044) — меняется только подача, не данные.

## Цель

Экран входа и дашборд отрисованы по прототипу v2 на базовом шаблоне TASK-053, с сохранением всей
существующей логики (аутентификация, счётчики).

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-054-report.md`.

- [ ] `/login` соответствует `page-login.jsx` (карточка входа, нейтральный знак, без логотипа — проект OSS).
- [ ] Дашборд соответствует `page-dashboard.jsx`: карточки-счётчики, сетка, использование токенов и плотности.
- [ ] Существующая логика входа и значения счётчиков не изменены — только шаблоны/стили.
- [ ] Тёмная тема и плотность из TASK-053 корректно применяются к обоим экранам.
- [ ] `ruff`/`mypy` зелёные (если затронут Python); PR `TASK-054: ...`; CI зелёный.
- [ ] Отчёт `handoff/outbox/TASK-054-report.md` написан.
- [ ] 🚨 Move-семантика inbox→archive (см. `handoff/README.md`).

## Артефакты

- `* src/admin/templates/login.html`
- `* src/admin/templates/dashboard.html`
- `* src/admin/static/css/` — при необходимости компонентные стили

## Ссылки

- Эталон: `sessions/2026-05-29-01-admin-design/artifacts/admin/page-login.jsx`, `page-dashboard.jsx`, `screens/01-dashboard.png`, `screens/01b-dashboard.png`
- Решение: [`docs/adr/0005-admin-v2-stack.md`](../../docs/adr/0005-admin-v2-stack.md)
