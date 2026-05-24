---
id: TASK-023
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - src/shared/services/event.py (add_outcome / update_outcome / delete_outcome)
  - src/shared/repositories/outcome.py
  - src/admin/templates/events/form.html
priority: high
estimate: L
---

# TASK-023: CRUD исходов через HTMX inline-edit (вкладка «Исходы»)

## Контекст

Третья бизнес-задача в админке. Закрывает вкладку «Исходы» из карточки события (вкладка «Данные» — TASK-022, «Результат» — TASK-024). **Первая HTMX-задача в админке** — задаёт паттерны для будущих inline-edit UI.

Серверная логика **полностью готова** (TASK-009):

- `OutcomeRepository`: `get_by_id` / `list_by_event` / `count_by_event` / `create` / `update` / `delete`.
- `EventService.add_outcome(event_id, label, sort_order, by_admin_id)` — с audit.
- `EventService.update_outcome(outcome_id, by_admin_id, **fields)` — с audit.
- `EventService.delete_outcome(outcome_id, by_admin_id)` — с audit + обработка `IntegrityError` → `OutcomeInUseError` (FK RESTRICT от Prediction).

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) — раздел «События → Вкладка «Исходы»»: «Список исходов с inline-редактированием (HTMX): `label`, `sort_order`. Кнопка «Добавить». Удаление — если на исход **нет** прогнозов. Кнопки `Опубликовать` неактивна, пока исходов меньше двух.»
- [`src/shared/services/event.py`](../../src/shared/services/event.py) — `add_outcome`, `update_outcome`, `delete_outcome` готовы.
- [`src/shared/exceptions.py`](../../src/shared/exceptions.py) — `OutcomeInUseError`, `OutcomeNotFoundError`.
- [`src/admin/templates/events/form.html`](../../src/admin/templates/events/form.html) — там сейчас «Исходы (TASK-023)» disabled — активировать.

## Перед стартом — pre-task cleanup PR

В origin/main `c437cbc` — last commit (archive TASK-022). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-022, новый шаг TASK-023.
- `state/DECISIONS.md` — 1 новая строка (selectinload pattern).
- `state/BACKLOG.md` — 2 новых пункта тех-долга.
- Новая сессия `sessions/2026-05-24-09-task-022-review/`.
- `handoff/inbox/TASK-023-admin-outcomes.md` — эта задача.

Branch: `chore/post-TASK-022-cowork-cleanup`, PR, merge. После — `feature/TASK-023-admin-outcomes`.

## Цель

Админ через UI на вкладке «Исходы» карточки события видит список исходов, может добавить/отредактировать/удалить через HTMX-фрагменты без полной перезагрузки страницы. Удаление при наличии прогнозов даёт alert «нельзя удалить». Все операции audit. Покрыто mock-based unit-тестами через TestClient. **Задаёт HTMX-паттерны** для TASK-024+ (inline-fixing итога — тоже HTMX).

## Definition of Done

### Step 1 — Routes в `src/admin/routes/outcomes.py`

- [ ] **Новый файл** (отдельный от `events.py` для модульности):
  ```python
  """HTMX-routes для inline CRUD исходов событий (TASK-023)."""

  from __future__ import annotations

  from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
  from fastapi.responses import HTMLResponse
  from fastapi_csrf_protect import CsrfProtect
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.db import SessionLocal
  from src.shared.exceptions import OutcomeInUseError, OutcomeNotFoundError, EventNotFoundError
  from src.shared.models import AdminUser
  from src.shared.services import EventService

  from ..app import templates
  from ..deps import current_admin

  __all__ = ["router"]

  router = APIRouter(prefix="/events/{event_id}/outcomes", tags=["outcomes"])


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  @router.get("", response_class=HTMLResponse)
  async def list_fragment(
      request: Request,
      event_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      """Fragment: список исходов с кнопкой «Добавить». Корневая загрузка вкладки."""
      event = await EventService(session).get_event(event_id, with_outcomes=True)
      if event is None:
          raise HTTPException(status_code=404)
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_list.html",
          context={"event_id": event_id, "outcomes": event.outcomes},
      )


  @router.get("/new", response_class=HTMLResponse)
  async def new_form_fragment(
      request: Request,
      event_id: int,
      admin: AdminUser = Depends(current_admin),
  ) -> HTMLResponse:
      """Fragment: inline-форма для добавления (заменяет «Добавить» кнопку)."""
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_form.html",
          context={"event_id": event_id, "outcome": None},
      )


  @router.post("", response_class=HTMLResponse)
  async def create(
      request: Request,
      event_id: int,
      label: str = Form(...),
      sort_order: int = Form(0),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse:
      """POST: добавить исход, вернуть обновлённый list-фрагмент."""
      await csrf_protect.validate_csrf(request)
      try:
          await EventService(session).add_outcome(
              event_id=event_id, label=label, sort_order=sort_order, by_admin_id=admin.id,
          )
      except EventNotFoundError:
          raise HTTPException(status_code=404)

      # Re-fetch list для свежего состояния
      event = await EventService(session).get_event(event_id, with_outcomes=True)
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_list.html",
          context={"event_id": event_id, "outcomes": event.outcomes},
      )


  @router.get("/{outcome_id}/edit", response_class=HTMLResponse)
  async def edit_form_fragment(
      request: Request,
      event_id: int,
      outcome_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      """Fragment: inline-форма для редактирования (заменяет строку списка)."""
      event = await EventService(session).get_event(event_id, with_outcomes=True)
      if event is None:
          raise HTTPException(status_code=404)
      outcome = next((o for o in event.outcomes if o.id == outcome_id), None)
      if outcome is None:
          raise HTTPException(status_code=404)
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_form.html",
          context={"event_id": event_id, "outcome": outcome},
      )


  @router.post("/{outcome_id}", response_class=HTMLResponse)
  async def update(
      request: Request,
      event_id: int,
      outcome_id: int,
      label: str = Form(...),
      sort_order: int = Form(0),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse:
      """POST: обновить исход, вернуть обновлённый list-фрагмент.

      Используем POST вместо PUT, потому что HTMX через `<form>` шлёт POST
      по умолчанию (избегаем `hx-method="put"` overrides).
      """
      await csrf_protect.validate_csrf(request)
      try:
          await EventService(session).update_outcome(
              outcome_id=outcome_id, by_admin_id=admin.id,
              label=label, sort_order=sort_order,
          )
      except OutcomeNotFoundError:
          raise HTTPException(status_code=404)

      event = await EventService(session).get_event(event_id, with_outcomes=True)
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_list.html",
          context={"event_id": event_id, "outcomes": event.outcomes},
      )


  @router.post("/{outcome_id}/delete", response_class=HTMLResponse)
  async def delete(
      request: Request,
      event_id: int,
      outcome_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse:
      """POST: удалить исход, вернуть обновлённый list или fragment с alert при ошибке."""
      await csrf_protect.validate_csrf(request)
      try:
          await EventService(session).delete_outcome(
              outcome_id=outcome_id, by_admin_id=admin.id,
          )
      except OutcomeInUseError:
          # Возвращаем список + alert (через context flag)
          event = await EventService(session).get_event(event_id, with_outcomes=True)
          return templates.TemplateResponse(
              request=request,
              name="outcomes/_list.html",
              context={
                  "event_id": event_id, "outcomes": event.outcomes,
                  "error": f"Нельзя удалить исход #{outcome_id}: на него есть прогнозы.",
              },
              status_code=status.HTTP_409_CONFLICT,
          )
      except OutcomeNotFoundError:
          raise HTTPException(status_code=404)

      event = await EventService(session).get_event(event_id, with_outcomes=True)
      return templates.TemplateResponse(
          request=request,
          name="outcomes/_list.html",
          context={"event_id": event_id, "outcomes": event.outcomes},
      )
  ```
- [ ] **Подключить в `src/admin/app.py`**: `app.include_router(outcomes_routes.router)`.

### Step 2 — Партиальные шаблоны

#### `src/admin/templates/outcomes/_list.html`

```html
{# Fragment: список исходов с кнопкой «Добавить». Корневая загрузка вкладки. #}
<div id="outcomes-container">
    {% if error %}
    <div class="alert alert-warning">{{ error }}</div>
    {% endif %}

    {% if outcomes %}
    <ol class="list-group list-group-numbered mb-3">
        {% for outcome in outcomes %}
        <li class="list-group-item d-flex justify-content-between align-items-center">
            <div>
                <strong>{{ outcome.label }}</strong>
                <small class="text-muted ms-2">sort: {{ outcome.sort_order }}</small>
            </div>
            <div>
                <button
                    type="button" class="btn btn-sm btn-outline-secondary"
                    hx-get="/events/{{ event_id }}/outcomes/{{ outcome.id }}/edit"
                    hx-target="#outcomes-container"
                    hx-swap="outerHTML">
                    <i class="bi bi-pencil"></i> Изм.
                </button>
                <form style="display:inline"
                      hx-post="/events/{{ event_id }}/outcomes/{{ outcome.id }}/delete"
                      hx-target="#outcomes-container"
                      hx-swap="outerHTML"
                      hx-confirm="Удалить исход «{{ outcome.label }}»?">
                    <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
                    <button type="submit" class="btn btn-sm btn-outline-danger">
                        <i class="bi bi-trash"></i>
                    </button>
                </form>
            </div>
        </li>
        {% endfor %}
    </ol>
    {% else %}
    <p class="text-muted">Исходов ещё нет. Добавьте минимум два, чтобы можно было опубликовать.</p>
    {% endif %}

    <button type="button" class="btn btn-primary"
            hx-get="/events/{{ event_id }}/outcomes/new"
            hx-target="#outcomes-container"
            hx-swap="outerHTML">
        <i class="bi bi-plus-lg"></i> Добавить исход
    </button>
</div>
```

#### `src/admin/templates/outcomes/_form.html`

```html
{# Fragment: inline-форма add/edit. Заменяет либо «Добавить» кнопку, либо строку списка. #}
<div id="outcomes-container">
    <form
        hx-post="{% if outcome %}/events/{{ event_id }}/outcomes/{{ outcome.id }}{% else %}/events/{{ event_id }}/outcomes{% endif %}"
        hx-target="#outcomes-container"
        hx-swap="outerHTML"
        class="card p-3 mb-3">
        <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
        <h6 class="card-title">
            {% if outcome %}Редактирование исхода #{{ outcome.id }}{% else %}Новый исход{% endif %}
        </h6>
        <div class="mb-2">
            <label class="form-label">Название</label>
            <input type="text" name="label" class="form-control" required
                   value="{{ outcome.label if outcome else '' }}"
                   autofocus>
        </div>
        <div class="mb-2">
            <label class="form-label">Порядок сортировки</label>
            <input type="number" name="sort_order" class="form-control"
                   value="{{ outcome.sort_order if outcome else 0 }}">
        </div>
        <div class="d-flex gap-2">
            <button type="submit" class="btn btn-primary btn-sm">Сохранить</button>
            <button type="button" class="btn btn-outline-secondary btn-sm"
                    hx-get="/events/{{ event_id }}/outcomes"
                    hx-target="#outcomes-container"
                    hx-swap="outerHTML">
                Отмена
            </button>
        </div>
    </form>
</div>
```

### Step 3 — Активировать вкладку «Исходы» в `events/form.html`

- [ ] **Заменить** в `events/form.html`:
  ```html
  <li class="nav-item">
      <a class="nav-link disabled" href="#">Исходы (TASK-023)</a>
  </li>
  ```
  на:
  ```html
  <li class="nav-item">
      <a class="nav-link {% if active_tab == 'outcomes' %}active{% endif %}"
         href="/events/{{ event.id }}?tab=outcomes">Исходы</a>
  </li>
  ```
- [ ] **Добавить tab content** для `outcomes`:
  ```html
  {% if active_tab == 'outcomes' %}
  <div hx-get="/events/{{ event.id }}/outcomes"
       hx-trigger="load"
       hx-swap="outerHTML">
      <div class="text-center py-4">
          <div class="spinner-border" role="status"></div>
          <p class="mt-2 text-muted">Загрузка исходов...</p>
      </div>
  </div>
  {% endif %}
  ```
  - `hx-trigger="load"` подгружает list-fragment при открытии вкладки.
- [ ] **`events/form.html` `edit_form` handler** должен принимать `tab="data" | "outcomes"` query param и рендерить соответствующее содержимое.

### Step 4 — Минорные правки

- [ ] **`OutcomeInUseError` уже есть в `src/shared/exceptions.py`** (TASK-009). Не дублировать.
- [ ] **`EventService.delete_outcome`** уже бросает `OutcomeInUseError` через try/IntegrityError — переиспользуем.
- [ ] **`EventService.get_event(with_outcomes=True)`** — каждый POST/DELETE handler делает 2 SQL: action + re-fetch. На admin-странице с ~5 исходами — приемлемо. Если станет горячо — `add_outcome` / `update_outcome` могут возвращать обновлённый list (отдельный refactor TASK-023a).

### Step 5 — HTMX-конфигурация

- [ ] **HTMX 2.x уже подключён** через CDN в `base.html` (TASK-019). Дополнительная настройка не нужна.
- [ ] **CSRF в HTMX-формах**: используем `<input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">` — стандартный form-data submit, `fastapi-csrf-protect` ловит. `hx-headers` для CSRF — альтернатива, но требует config token_location='header', оставим как есть.
- [ ] **`hx-confirm`** для delete — встроенный HTMX confirm-popup. Достаточно для MVP, не нужны JS-modal'ы.
- [ ] **`#outcomes-container` ID** — корневой контейнер swap. Все fragments начинаются с `<div id="outcomes-container">` чтобы `hx-swap="outerHTML"` корректно заменял весь блок.

### Step 6 — Тесты

#### `tests/unit/admin/test_outcomes_handler.py` (новый)

8-10 unit через TestClient (mock SessionLocal в middleware + override current_admin):

- [ ] `test_unauthorized_redirects_to_login`.
- [ ] `test_list_fragment_returns_outcomes_html` — `<ol class="list-group">` присутствует, есть исходы.
- [ ] `test_list_fragment_empty_shows_hint` — «Исходов ещё нет».
- [ ] `test_new_form_fragment_returns_form_html` — `<form hx-post=".../outcomes">`.
- [ ] `test_create_outcome_returns_updated_list`.
- [ ] `test_edit_form_fragment_pre_fills_values` — value=existing label.
- [ ] `test_update_outcome_returns_updated_list`.
- [ ] `test_delete_outcome_success_returns_updated_list`.
- [ ] `test_delete_outcome_in_use_returns_409_with_alert` — mock service бросает `OutcomeInUseError`, response 409, в HTML есть alert.
- [ ] `test_delete_unknown_outcome_404`.

#### Существующие integration-тесты `EventService` уже покрывают сервис

`add_outcome`, `update_outcome`, `delete_outcome` покрыты в TASK-009 (`tests/integration/services/test_event_service.py`). Не дублируем.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая ~9 новых.
- [ ] `uv run pytest tests/integration -m integration` — без падений (новых integration нет).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - Создать event через TASK-022 UI.
  - Открыть `/events/{id}?tab=outcomes` → spinner → list fragment.
  - «Добавить исход» → inline-форма → submit → новый исход в списке.
  - «Изм.» → inline-edit → submit → label обновлён.
  - «Trash» → confirm dialog → удалено.
  - Сделать prediction в БД через psql на этот event/outcome.
  - Попытка удалить тот же исход → 409 + alert «нельзя удалить, есть прогнозы».
  - Publish event → требует ≥2 исхода (TASK-022 уже это enforce'ит).
- [ ] Ветка `feature/TASK-023-admin-outcomes`, Conventional Commits:
  - `feat(admin): outcomes routes (list/new/create/edit/update/delete fragments)`
  - `feat(admin): outcomes/_list.html + _form.html partials`
  - `feat(admin): activate Исходы tab in events/form.html with hx-trigger="load"`
  - `test(admin): outcomes handler tests (~9 unit)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-023-report.md`, задача → `handoff/archive/TASK-023-admin-outcomes/task.md`.

## Артефакты

```
+ src/admin/routes/outcomes.py                       # 6 HTMX-handlers
+ src/admin/templates/outcomes/_list.html            # fragment списка
+ src/admin/templates/outcomes/_form.html            # fragment add/edit
* src/admin/templates/events/form.html               # activate Исходы tab + hx-trigger="load"
* src/admin/routes/events.py                         # edit_form принимает tab=outcomes (если не было)
* src/admin/app.py                                   # +outcomes router
+ tests/unit/admin/test_outcomes_handler.py          # ~9 тестов
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — раздел «События → Вкладка Исходы»
- [src/shared/services/event.py](../../src/shared/services/event.py) — `add_outcome`, `update_outcome`, `delete_outcome` готовы
- [src/shared/exceptions.py](../../src/shared/exceptions.py) — `OutcomeInUseError`, `OutcomeNotFoundError`
- [src/admin/templates/events/form.html](../../src/admin/templates/events/form.html) — там disabled-ссылка на Исходы, активировать

## Подсказки исполнителю

- **HTMX-паттерн `hx-swap="outerHTML"`** на корневом контейнере `#outcomes-container`: каждый fragment начинается с того же `<div id="outcomes-container">` — HTMX заменяет ВЕСЬ блок включая обёртку, что даёт чистый refresh без вложенных контейнеров.
- **`hx-trigger="load"`** — fragment подгружается при открытии вкладки. Spinner — визуальная заглушка до окончания загрузки.
- **`hx-confirm`** — встроенный HTMX-confirm. JS `window.confirm()` под капотом. Достаточно для MVP; полноценный modal через Bootstrap — TASK-026+ когда захотим.
- **CSRF в HTMX-формах**: hidden `<input name="csrf_token">` в каждой форме. Альтернатива (header через `hx-headers`) требует config token_location='header' в CsrfProtect — лишняя ceremony.
- **`get_event(with_outcomes=True)` + re-fetch** после каждого write — простой подход. Если станет горячо — handler возвращает обновлённый list inline (без отдельного SELECT), но это микро-оптимизация.
- **POST вместо PUT/DELETE для update/delete**: HTMX через `<form>` шлёт POST по умолчанию. Routes именованы `/outcomes/{id}` (POST = update) и `/outcomes/{id}/delete` (POST = delete) — REST не строгий, но handler-логика чёткая.
- **`outcome.id` в Jinja**: модель `Outcome` имеет `id` (см. `src/shared/models/outcome.py`). В шаблоне работает обычное `{{ outcome.id }}`.
- **`button type="button"`** для `hx-get`-кнопок (Изм., Добавить, Отмена) — чтобы не submit'ились в случайно вложенной форме. У update/create `<button type="submit">` остаётся.
- **`autofocus`** на label-input при new form — UX улучшение.

## Что НЕ делать

- **Не делать drag-drop sort_order** — преждевременно. Sort_order вручную через input.
- **Не делать modal-confirm через Bootstrap** — `hx-confirm` (window.confirm) достаточен. Modal с CSRF — overengineering для MVP.
- **Не делать pagination исходов** — у события 2-5 исходов обычно, без pagination.
- **Не возвращать вкладку «Результат»** — это TASK-024.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости.
- Не зеркалить в Drive вручную.
