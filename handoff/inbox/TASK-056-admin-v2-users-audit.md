---
id: TASK-056
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

# TASK-056: Переверстать пользователей и аудит-лог в дизайн v2

## Контекст

Завершающая задача поэкранного перевода админки на дизайн v2 (после TASK-053): пользователи
(`page-users.jsx`, список + карточка) и аудит-лог (`page-audit.jsx`). Логика уже реализована
(TASK-025/026) — переверстывается подача.

Страница «Идеи интерфейсов» (`page-roadmap.jsx`) — это каталог пост-MVP-фич из прототипа, а **не**
экран для реализации. В продакшен-админку её переносить **не нужно**; она остаётся в прототипе как
материал для будущих cowork-сессий.

## Цель

Экраны пользователей и аудит-лога отрисованы по прототипу v2 на базовом шаблоне TASK-053 без
регрессий в логике.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-056-report.md`.

- [ ] Список и карточка пользователя соответствуют `page-users.jsx` (включая флаг `is_blocked`).
- [ ] Аудит-лог соответствует `page-audit.jsx`; таблица учитывает плотность.
- [ ] Страница roadmap НЕ реализуется в продакшене (осознанно опущена).
- [ ] Тёмная тема и плотность применяются к обоим экранам.
- [ ] `ruff`/`mypy` зелёные (если затронут Python); PR `TASK-056: ...`; CI зелёный.
- [ ] Отчёт `handoff/outbox/TASK-056-report.md` написан.
- [ ] 🚨 Move-семантика inbox→archive (см. `handoff/README.md`).

## Артефакты

- `* src/admin/templates/users/...`
- `* src/admin/templates/audit/...`

## Ссылки

- Эталон: `sessions/2026-05-29-01-admin-design/artifacts/admin/page-users.jsx`, `page-audit.jsx`
- Решение: [`docs/adr/0005-admin-v2-stack.md`](../../docs/adr/0005-admin-v2-stack.md)
