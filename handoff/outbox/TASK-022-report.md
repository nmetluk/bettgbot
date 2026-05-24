---
task: TASK-022
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/64
branch: feature/TASK-022-admin-events
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/63 (pre-task cleanup)
commits:
  - 3c5dfdc chore(handoff): take TASK-022 in progress
  - 9f1d8dd feat(admin): CsrfTokenMiddleware (DRY csrf_token via request.state) + admin info in sidebar
  - c30e775 feat(repositories): EventRepository.list_for_admin_with_predictions_count + count_for_admin_with_period + AdminEventPeriod
  - 4036e9c feat(admin): events routes (list/new/create/edit/update/publish/unpublish) + list/form templates + sidebar Events active
  - b2eaf23 test: EventService admin filters (7 integration) + events handler (9 unit); selectinload Category to avoid GROUP BY conflict
---

# Отчёт по TASK-022: CRUD событий в админке + CSRF middleware + admin-info

## Сводка

**Step 0** закрыл TASK-021 open-question #1: новый `CsrfTokenMiddleware` (ASGI) генерирует `csrf_token` в `request.state` + ставит `fastapi-csrf-token` cookie для всех GET кроме `/static/*` и `/healthz`. Шаблоны (`base.html`, `login.html`, `categories/{list,form}.html`, `events/{list,form}.html`) читают `{{ request.state.csrf_token }}` — handler'ам больше не нужно генерировать. Sidebar показывает имя админа (`admin.full_name or admin.login`) через `admin or request.state.admin`. Events ссылка активирована.

POST handler'ы (`_render_login_error`, `_render_form_with_error`) оставлены с ручной генерацией — middleware POST не покрывает. Это явное исключение.

**Step 1-2**: `EventRepository.list_for_admin_with_predictions_count` — один SQL: LEFT JOIN `Prediction` + GROUP BY `event.id` + `count`. Фильтры через `_admin_filters` (status) + новый `_period_filters` (next7/past). `AdminEventPeriod = Literal["all","next7","past"]` экспортирован. **Compromise по join**: `selectinload(Event.category)` вместо `joinedload` — PostgreSQL ругается `GroupingError: column "category_1.id" must appear in the GROUP BY clause` при JOIN+GROUP BY без перечисления всех колонок. `selectinload` делает один отдельный SELECT по собранным category_ids — на admin-странице со 50 событиями приемлемо.

**Step 4-5**: 7 handlers в `routes/events.py`. `events/list.html`: фильтры в шапке (category/status/period как `<select>`), таблица с status-бэйджем через Jinja global `now()`, pagination (prev/next с QS-сохранением фильтров). `events/form.html`: `datetime-local` inputs, JSON metadata `textarea`, Bootstrap `nav-tabs` (Данные active, Исходы/Результат disabled), форма publish/unpublish.

**Step 6**: 7 integration (predictions count, фильтры category/status_draft/status_published_open/period_next7/period_past, count соответствует list len) + 9 unit handler (unauthorized → login, list renders, new form, create success, invalid metadata 400, edit with tabs, publish success, publish not_enough_outcomes flash, unpublish).

## Изменённые файлы

```
* src/admin/app.py                                # +Jinja global now() + register events router + middleware order
* src/admin/auth/middleware.py                    # +CsrfTokenMiddleware
* src/admin/routes/login.py                       # убрана ручная csrf в GET; _render_login_error для POST-error
* src/admin/routes/categories.py                  # убрана ручная csrf в GET; _render_form для POST-error
* src/admin/templates/base.html                   # sidebar +admin info + Events active + request.state.csrf_token
* src/admin/templates/login.html                  # csrf via request.state
* src/admin/templates/categories/list.html        # то же
* src/admin/templates/categories/form.html        # то же
* src/shared/repositories/event.py                # +AdminEventPeriod + list_for_admin_with_predictions_count + count_for_admin_with_period
* src/shared/services/event.py                    # +list_admin_with_counts + count_admin
+ src/admin/routes/events.py                      # 7 handlers
+ src/admin/templates/events/list.html            # filters + table + pagination
+ src/admin/templates/events/form.html            # form + nav-tabs + publish/unpublish
+ tests/integration/services/test_event_service_admin.py  # 7 тестов
+ tests/unit/admin/test_events_handler.py         # 9 тестов
* handoff/inbox/TASK-022-...md → archive/TASK-022-admin-events/task.md
+ handoff/outbox/TASK-022-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    141 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 72 source files
pytest -m "not integration"      194 passed (было 185; +9 events handler)
pytest tests/integration         109 passed (было 102; +7 events admin)

CI PR #64 — все 4 job'а зелёные:
  Lint (ruff)                              10s
  Typecheck (mypy)                         23s
  Tests (pytest, unit)                     20s
  Integration                              52s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
# .env: ENVIRONMENT=dev (Secure cookie выключен для localhost)
make up && make migrate
make admin.create LOGIN=admin PASSWORD="strong!"
make admin  # http://127.0.0.1:8000

# Browser flow:
# /login → форма с CSRF
# POST → / dashboard, sidebar показывает «admin»
# Sidebar «События» → /events (фильтры в шапке)
# /events/new → форма с категориями + datetime-local + metadata-JSON
# Submit → 302 на /events/{id} → edit-форма с nav-tabs (Данные active)
# Publish с <2 исходами → 302 ?error=not_enough_outcomes + alert
# Создать 2 outcome через psql → publish → событие опубликовано
```

## Что не сделано / вынесено

1. **Вкладки Исходы / Результат** — только disabled-ссылки в nav-tabs. Это TASK-023 и TASK-024.
2. **EventInvalidDatesError** для `predictions_close_at > starts_at` (CHECK `ck_event_close_before_start`) — не добавил. При нарушении сейчас вылетит сырой `IntegrityError` → 500. Если ловить — обработка в `EventService.create_event` / `update_event` через try/IntegrityError + mapping. Опциональный шаг из task.md, пропустил для краткости.
3. **Восстановление архивных событий** — спека явно «не делать». Текст «Восстановление вне scope MVP» в `form.html`.
4. **HTMX inline-edit, drag-drop sort** — преждевременно.
5. **Pagination через HTMX** — обычный server-render.

## Открытые вопросы для проектировщика

1. **`selectinload(Category)` вместо `joinedload`** в `list_for_admin_with_predictions_count` — потому что PostgreSQL `GROUP BY event.id` не покрывает все Category-колонки, которые joinedload добавляет в SELECT. Selectinload делает один отдельный SELECT по category_ids. На admin-странице с 50 событиями (1-2 категории обычно) — мизерная overhead. Если хотим один запрос — нужно либо все Category-колонки в GROUP BY, либо subquery + outerjoin вместо joinedload. Согласуем?
2. **`update_event` при невалидных датах редиректит на edit с `?error=invalid_input`** вместо рендера формы с введёнными значениями (как в `create_event`). Это потеря пользовательского ввода. Если важно — переделать на полноценный re-render. Сейчас экономия кода.
3. **`EventInvalidDatesError` не добавил.** В task.md оно «опционально на этой итерации». Если хотим — отдельной мелкой задачей.
4. **`event.category.name` в `events/list.html`** — работает потому что `selectinload`. Если когда-то перейдём на subquery без eager-load, поломается. Записать как тех-долг?
5. **CsrfTokenMiddleware генерирует cookie для всех GET (включая `/login` и `/healthz`).** Я исключил `/healthz` и `/static/*`. `/login` оставил — там форма нужна. Если хотим строже (только authed-GET) — добавь `state.get("admin")` гард обратно, плюс перенеси CSRF generation для login в handler.
6. **Глобальный `now()` в Jinja** работает per-render (вызов функции), не кешируется. Это правильно для status-бэйджей. Не вызывайте дважды в одном шаблоне — но шаблон сейчас вызывает только в условии.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-022: CRUD событий в админке (вторая большая бизнес-задача). `CsrfTokenMiddleware` (ASGI, генерирует `csrf_token` в `request.state` + cookie для всех GET кроме `/static/*` и `/healthz`) — закрывает TASK-021 open-q #1. Шаблоны переписаны на `{{ request.state.csrf_token }}` (DRY). Admin-info в sidebar (`admin.full_name or admin.login`). `EventRepository.list_for_admin_with_predictions_count` + `count_for_admin_with_period` + `AdminEventPeriod` (selectinload Category т.к. joinedload + GROUP BY конфликт). `EventService.list_admin_with_counts` + `count_admin`. 7 handlers (list/new/create/edit/update/publish/unpublish), 2 шаблона (filters+pagination+nav-tabs+datetime-local+JSON metadata). 16 новых тестов (194 unit + 109 integration). PR [#64](https://github.com/nmetluk/bettgbot/pull/64) → squash `032aa42`. Pre-task cleanup [#63](https://github.com/nmetluk/bettgbot/pull/63).
```

## Метрики

- Файлов добавлено: 5 (events route + 2 шаблона + 2 теста + report)
- Файлов изменено: 10 (app, middleware, login, categories, base.html, login.html, categories list/form html, event repo, event service)
- Тестов добавлено: 16 (всего 194 unit + 109 integration; было 185+102)
- Время на выполнение: ~75 мин (включая cleanup PR, разбор joinedload+GROUP BY, выбор selectinload, отладка middleware-порядка)
