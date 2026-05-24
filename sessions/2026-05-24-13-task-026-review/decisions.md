# Решения — task-026-review

**Все 6 — keep:**

| # | Решение | Обоснование |
|---|---|---|
| 1 | `{% include "audit/_preview.html" %}` в list.html — DRY | Один layout для preview между initial render и collapse-fragment |
| 2 | Pagination без HTMX (обычный `<a href>` с QS) | Page reload OK для админ-интерфейса. `hx-boost` — overengineering |
| 3 | `datetime-local` naive → UTC явно в `_parse_iso_date` | Label «(UTC)» в форме. JS-конверсия local TZ — отдельная задача |
| 4 | `action` точное совпадение через `==` (не substring) | Не критично для MVP. Substring `ilike` — мелкое улучшение если потребуется |
| 5 | `AdminUserRepository.list_all` без service-обёртки | Convention: нет бизнес-логики → handler зовёт repo напрямую |
| 6 | `json.dumps(ensure_ascii=False)` для pretty-print | Кириллица читаема. Jinja HTML-escape не ломает `<pre><code>` |

## Этап 3 закрыт — 8/8 задач

См. `brief.md` секция «Итоги Этапа 3» — суммарно ~7 часов, 96 тестов, 0 блокировок.

## Паттерны зафиксированные в Этапе 3

1. **CSRF middleware** через `request.state.csrf_token` (TASK-022).
2. **HTMX**: корневой `#X-container` + `hx-swap="outerHTML"` (TASK-023).
3. **HTMX per-row** `#X-details-{id}` для table-rows (TASK-026).
4. **`selectinload`** при JOIN+GROUP BY в admin-методах с aggregations (TASK-022).
5. **`include_inactive=True`** default для admin-list-методов (TASK-021).
6. **`Settings.environment`** + conditional `Secure=` cookie (TASK-021).
7. **bcrypt напрямую** без passlib (TASK-019/020).
8. **Timing-attack mitigation** dummy `bcrypt.checkpw` в auth-сервисах (TASK-020).
9. **`{% include "X/_preview.html" %}`** для DRY initial+HTMX-fragment (TASK-026).
10. **Test pattern**: `GET /login` для CSRF без service-mock'ов (TASK-025).

Эти паттерны переходят в Этап 4 как baseline.
