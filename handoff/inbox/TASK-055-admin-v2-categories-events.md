---
id: TASK-055
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: ["TASK-053"]
related:
  - docs/adr/0005-admin-v2-stack.md
  - sessions/2026-05-29-01-admin-design/artifacts/admin/
priority: normal
estimate: L
---

# TASK-055: Переверстать категории, список событий и карточку события в дизайн v2

## Контекст

Продолжение поэкранного перевода админки на дизайн v2 (после TASK-053). Эта задача — самая объёмная
часть UI: категории (`page-categories.jsx`), список событий (`page-events-list.jsx`) и карточка
события с блоком фиксации результата (`page-event-detail.jsx`). Логика CRUD и фиксации итога уже
реализована (TASK-021/022/024) — переверстывается подача, бизнес-логика не трогается.

## Цель

Экраны категорий, списка событий и карточки события отрисованы по прототипу v2 на базовом шаблоне
TASK-053; HTMX-взаимодействия и фиксация результата работают как прежде.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-055-report.md`.

- [ ] Список и формы категорий соответствуют `page-categories.jsx`.
- [ ] Список событий с фильтрами (категория, статус) соответствует `page-events-list.jsx`; таблица учитывает плотность.
- [ ] Карточка события соответствует `page-event-detail.jsx`: данные + список исходов + блок результата (радио итогового исхода как `.result-opt` в прототипе).
- [ ] Все существующие HTMX-обновления, публикация и фиксация результата работают без регрессий.
- [ ] Тёмная тема и плотность применяются ко всем трём экранам.
- [ ] `ruff`/`mypy` зелёные (если затронут Python); PR `TASK-055: ...`; CI зелёный.
- [ ] Отчёт `handoff/outbox/TASK-055-report.md` написан.
- [ ] 🚨 Move-семантика inbox→archive (см. `handoff/README.md`).

## Артефакты

- `* src/admin/templates/categories/...`
- `* src/admin/templates/events/...`
- `* src/admin/static/css/` — компонентные стили таблиц/форм/бейджей

## Ссылки

- Эталон: `sessions/2026-05-29-01-admin-design/artifacts/admin/page-categories.jsx`, `page-events-list.jsx`, `page-event-detail.jsx`, `screens/01-02-event.png`, `screens/02-02-event.png`, `screens/03-result.png`
- Решение: [`docs/adr/0005-admin-v2-stack.md`](../../docs/adr/0005-admin-v2-stack.md)

## Подсказки исполнителю

- Объём большой — при необходимости разбей реализацию на отдельные коммиты внутри одной ветки/PR (категории → список событий → карточка), но закрывай задачу целиком.
- Блок результата критичен (фиксация итога + отметка прогнозов в одной транзакции) — следи, чтобы переверстка не сломала форму и её submit.
