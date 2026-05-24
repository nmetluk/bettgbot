# Решения — task-023-review

**4 keep + 2 в тех-долг + 1 паттерн зафиксирован:**

| # | Решение | Обоснование |
|---|---|---|
| 1 (**тех-долг**) | `OutcomeService update_outcome` / `delete_outcome` no-op при несуществующем outcome_id — BACKLOG | service сейчас делает UPDATE/DELETE WHERE id=X без affected rows check. Handler возвращает list (выглядит как успех). На MVP race conditions редки. Триггер — реальный кейс админа |
| 2 (**паттерн**) | **HTMX корневой `#X-container` + `hx-swap="outerHTML"`** — convention для всех HTMX-fragments в админке | Fragment self-contained, легко переиспользуется в разных контекстах. Альтернатива (`innerHTML` на внешнем wrap) требует «чистого» fragment без wrap. Применяется в TASK-023 (`outcomes`), будущих TASK-024/025/026 |
| 3 (**тех-долг**) | `EventService.add_outcome` не валидирует `event.is_archived` — BACKLOG | UI не показывает кнопку для архивных, но через прямой URL можно создать. Минорный defensive UX. Service-level guard через raise `EventNotPredictableError(reason="archived")` либо нового exception |
| 4 (keep) | CSRF token expiration в multi-tab — keep security trade-off | Пользователь видит 403, обновляет страницу, делает заново. Нормально |
| 5 (keep) | `OutcomeInUseError` → 409 + `_list.html` с alert (не отдельный `_error.html`) | Пользователь видит и обновлённый список, и причину ошибки в одном месте. Идиоматично для HTMX |
| 6 (keep) | HTMX 2.x через CDN — на MVP keep | Production-self-hosted — в TASK-027 (deployment) при необходимости offline |

## HTMX-pattern «корневой контейнер + outerHTML» — фиксация

Все HTMX-fragments в админке следуют паттерну:

1. Партиал начинается с `<div id="X-container">...</div>` (где X — feature name, например `outcomes`).
2. Все HTMX-операции (`hx-get`, `hx-post`) направлены на `hx-target="#X-container"` + `hx-swap="outerHTML"`.
3. Fragment **полностью заменяет** свой root-контейнер на обновлённый.

Преимущества:
- Fragment self-contained (нет внешнего wrap'а, можно использовать в любой обвязке).
- `outerHTML` гарантирует, что после swap'а DOM-структура остаётся правильной — никаких вложенных контейнеров.
- Спиннер-placeholder на родительском уровне (`hx-trigger="load"`) подменяется первым же fragment'ом — естественная инициализация.

Применяется в:
- TASK-023: `outcomes/{_list,_form}.html` с `#outcomes-container`.
- Будущие TASK-024+: `events/_result_tab.html` (если выносить вкладку «Результат» как HTMX-fragment), TASK-026 audit-log details через HTMX.

## Тех-долг (новые пункты в BACKLOG)

1. **`OutcomeService update_outcome` / `delete_outcome` → raise `OutcomeNotFoundError`** при отсутствии outcome через `get_by_id` check перед write. +1 SELECT на write. Триггер — реальный кейс админа.

2. **`EventService.add_outcome` валидирует `event.is_archived = false`** — service-level guard. Через get_event + raise. Минор defensive UX.
