# Решения — task-022-review

**5 keep + 1 в тех-долг + 1 паттерн зафиксирован:**

| # | Решение | Альтернативы | Обоснование |
|---|---|---|---|
| 1 (**паттерн**) | **`selectinload` вместо `joinedload` при JOIN+GROUP BY** для eager-loading отношений | (a) Все колонки relationship в GROUP BY; (b) Subquery + outerjoin | `joinedload` добавляет все колонки relation в SELECT, ломает GROUP BY (`column must appear in GROUP BY clause`). `selectinload` делает один отдельный SELECT по собранным IDs — на admin-страницах с ~50 строками мизерный overhead, выигрыш — простой и читаемый код. **Применять во всех admin-list-методах с aggregations.** |
| 2 (**тех-долг**) | `update_event` при невалидных датах редиректит на edit с `?error=invalid_input` — **записать в BACKLOG** «re-render формы с введёнными значениями» | Сейчас же переделать на полноценный re-render | Потеря user input при ошибке — UX-баг, но не блокер. Триггер фикса — feedback админа в проде. `create_event` уже делает re-render с error — desyn между create и update оставляет шероховатость, но не критично |
| 3 | `EventInvalidDatesError` не добавлен (CHECK `ck_event_close_before_start` бросает `IntegrityError` → 500 при нарушении) — keep | Добавить с try/IntegrityError + mapping | task.md помечал как опциональный. На MVP admin сам ставит корректные даты; HTML-форма не валидирует. Триггер — когда админ реально натолкнётся. Запишу в BACKLOG как defensive UX |
| 4 | `event.category.name` в шаблоне `events/list.html` — keep coupling с `selectinload` | Subquery без eager-load + лень-загрузка имени через `<td>{{ event.category_id }}</td>` (просто ID) | Coupling зафиксирован паттерном (#1). Шаблон удобнее с именем, чем с ID. Не записываю в тех-долг — это design-decision, не runtime-баг |
| 5 | `CsrfTokenMiddleware` cookie для всех GET (включая `/login`) — keep | Гард `state.get("admin")` для только authed-GET | `/login` нужна CSRF в форме. Если найдём атаку через CSRF-cookie на не-authed страницах — добавим гард. На MVP — безопасно. Исключения: `/static/*` и `/healthz` |
| 6 | Глобальный Jinja `now()` per-render (вызов функции, не кэш) — keep | Сделать `now` переменной в context | Per-render правильно для status-бэйджей (свежее время на каждом рендере). Не используем дважды в одном шаблоне |

## Тех-долг (новые пункты в BACKLOG)

1. **`update_event` re-render с введёнными значениями** при невалидных датах / metadata JSON — паритет с `create_event`. Триггер — UX feedback админа.

2. **`EventInvalidDatesError` для `ck_event_close_before_start`** — добавить try/IntegrityError mapping в `EventService.create_event` / `update_event`. Default 500 на нарушении CHECK — некрасиво. Триггер — реальный кейс админа.

## Паттерн «selectinload при JOIN+GROUP BY» — фиксация

Все admin-list-методы с aggregations (COUNT, SUM) и eager-loaded relationships используют `selectinload(Relation)`, не `joinedload(Relation)`. SQLAlchemy issue: joinedload требует все колонки relation в `GROUP BY`, что несовместимо с aggregation patterns.

Применяется к:
- `EventRepository.list_for_admin_with_predictions_count` (TASK-022) — `selectinload(Event.category)`.
- Будущим: `UserRepository.list_with_prediction_counts` (TASK-025), `AuditLogRepository.list_with_admin` (TASK-026).
