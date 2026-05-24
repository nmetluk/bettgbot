---
id: TASK-022
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - docs/03-data-model.md
  - src/shared/services/event.py
  - src/shared/repositories/event.py
  - src/admin/auth/
priority: high
estimate: L
---

# TASK-022: CRUD событий в админке + CSRF middleware + admin-info

## Контекст

Вторая большая бизнес-задача в админке. Закрывает «вкладку Данные» из спеки `docs/05-admin-spec.md` (вкладки «Исходы» и «Результат» — TASK-023 и TASK-024). Заодно Step 0 — закрытие двух change-решений из TASK-021 review: CSRF middleware (DRY вместо генерации в каждом handler'е) + рендеринг имени админа в sidebar.

Серверная логика **частично готова** ([TASK-007](../archive/TASK-007-repositories), [TASK-009](../archive/TASK-009-services)):

- `EventService.create_event` / `update_event` / `publish_event` / `unpublish_event` — есть.
- `EventService.list_for_admin(category_id, status, offset, limit)` — есть, `status: Literal["all", "draft", "published", "archived"]`. **НЕ хватает фильтра по периоду** (`next7days`, `past`).
- `EventService.count_for_admin` — для пагинации.
- `EventRepository.list_for_admin_with_predictions_count` — **НЕ существует**, нужен новый метод для admin-таблицы с колонкой «прогнозов».

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «События» (список с фильтрами + status-badges + карточка с вкладками).
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — `Event(title, description, category_id, metadata, starts_at, predictions_close_at, is_published, is_archived, archived_at, result_outcome_id)`. CHECK invariants.
- [`src/shared/services/event.py`](../../src/shared/services/event.py) + [`src/shared/repositories/event.py`](../../src/shared/repositories/event.py) — образец.
- [`src/admin/routes/categories.py`](../../src/admin/routes/categories.py) (TASK-021) — образец admin CRUD-handler'а.
- [`src/admin/auth/middleware.py`](../../src/admin/auth/middleware.py) — образец ASGI middleware.

## Перед стартом — pre-task cleanup PR

В origin/main `0baa533` — last commit (archive TASK-021). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-021, новый шаг TASK-022.
- `state/DECISIONS.md` — 3 новых строки (CSRF middleware, admin list_inactive=True default, sidebar roadmap).
- Новая сессия `sessions/2026-05-24-08-task-021-review/`.
- `handoff/inbox/TASK-022-admin-events.md` — эта задача.

Branch: `chore/post-TASK-021-cowork-cleanup`, PR, merge. После — `feature/TASK-022-admin-events`.

## Цель

Админ через UI создаёт/редактирует/публикует/снимает с публикации события, видит список с фильтрами категория/статус/период и счётчиком прогнозов. Карточка события — вкладки Bootstrap nav-tabs: «Данные» (форма редактирования + кнопки publish/unpublish), «Исходы» (заглушка TASK-023), «Результат» (заглушка TASK-024). Все write-операции пишутся в audit. Step 0 — CSRF middleware вставляет `request.state.csrf_token` для всех GET под auth, рендеринг `admin.full_name` в sidebar.

## Definition of Done

### Step 0 — `CsrfMiddleware` + admin-info в sidebar

#### 0.1 — `src/admin/auth/middleware.py` — добавить `CsrfMiddleware`

- [ ] **Новый ASGI middleware** в том же файле (или отдельном `src/admin/auth/csrf.py`):
  ```python
  from fastapi_csrf_protect import CsrfProtect


  class CsrfTokenMiddleware:
      """Генерирует CSRF-токен для GET-запросов под auth, вставляет в request.state."""

      def __init__(self, app: ASGIApp) -> None:
          self.app = app

      async def __call__(self, scope, receive, send) -> None:
          if scope["type"] != "http":
              await self.app(scope, receive, send)
              return

          request = Request(scope, receive=receive)
          # Только для GET — POST'ам токен уже передан через форму.
          # Только если admin в state — middleware RequireAdminMiddleware
          # должен сработать ДО этого.
          if request.method == "GET" and scope.get("state", {}).get("admin") is not None:
              csrf_protect = CsrfProtect()
              csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
              scope["state"]["csrf_token"] = csrf_token

              async def send_with_csrf_cookie(message):
                  if message["type"] == "http.response.start":
                      # set_csrf_cookie через прямую вставку Set-Cookie
                      s = get_settings()
                      cookie_parts = [
                          f"fastapi-csrf-token={signed_token}",
                          "HttpOnly",
                          "SameSite=Lax",
                          "Path=/",
                      ]
                      if s.environment != "dev":
                          cookie_parts.append("Secure")
                      headers = list(message.get("headers", []))
                      headers.append((b"set-cookie", "; ".join(cookie_parts).encode("latin-1")))
                      message = {**message, "headers": headers}
                  await send(message)

              await self.app(scope, receive, send_with_csrf_cookie)
              return

          await self.app(scope, receive, send)
  ```
- [ ] **Подключить в `src/admin/app.py` ПОСЛЕ `RequireAdminMiddleware`** — порядок важен:
  ```python
  app.add_middleware(CsrfTokenMiddleware)  # после RequireAdminMiddleware
  app.add_middleware(RequireAdminMiddleware)
  ```
  Starlette вызывает middleware в **обратном порядке** добавления, поэтому Require... обрабатывает запрос первым, потом CsrfToken... Делает `state["admin"]` доступным.
- [ ] **Альтернатива — Jinja2 context_processor**: подключить через `templates.env.globals["csrf_token"] = lambda req: req.state.csrf_token`. Реализация исполнителя, если удобнее. Главное — без правок каждого handler'а.

#### 0.2 — Удалить дублирование CSRF из handler'ов

- [ ] **В `src/admin/routes/login.py`** — `login_form` сейчас сам генерирует CSRF. После middleware можно убрать `csrf_protect.generate_csrf_tokens()` и `set_csrf_cookie` из handler — middleware сделает это. Шаблон читает из `request.state.csrf_token`.
- [ ] **В `src/admin/routes/categories.py`** — аналогично убрать ручную генерацию в `new_form` и `edit_form`. POST handler'ы оставить как есть (там `validate_csrf` — это уже verify, не generate).
- [ ] **POST handler'ы оставить** с `await csrf_protect.validate_csrf(request)` — verify не меняется.

#### 0.3 — `admin.full_name` в sidebar

- [ ] **Universal admin в context**: реализовать Jinja2 context_processor через `templates.env.globals["admin"] = lambda req: req.state.admin if hasattr(req.state, "admin") else None`. Или передавать в `TemplateResponse.context` каждого handler'а (overhead).
- [ ] **В `src/admin/templates/base.html`** — добавить в sidebar выше logout-формы:
  ```html
  {% if admin or request.state.admin %}
  {% set _adm = admin or request.state.admin %}
  <li class="nav-item mt-auto pt-3">
      <small class="text-muted d-block px-2">
          <i class="bi bi-person-circle"></i>
          {{ _adm.full_name or _adm.login }}
      </small>
  </li>
  {% endif %}
  ```
  - Использует `admin or request.state.admin` для совместимости (если handler передаёт явно — берём оттуда, иначе из state).

#### 0.4 — Шаблоны на `request.state.csrf_token`

- [ ] **`src/admin/templates/login.html`**: `<input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">` (вместо `{{ csrf_token }}`).
- [ ] **`src/admin/templates/categories/list.html`** + **`form.html`** — то же.
- [ ] **`src/admin/templates/base.html` logout-form** — то же.

### Step 1 — `EventRepository.list_for_admin_with_predictions_count`

- [ ] **В `src/shared/repositories/event.py`** добавить:
  ```python
  from typing import Literal

  AdminEventPeriod = Literal["all", "next7", "past"]


  class EventRepository:
      # ... existing methods

      async def list_for_admin_with_predictions_count(
          self,
          *,
          category_id: int | None = None,
          status: AdminEventStatus = "all",
          period: AdminEventPeriod = "all",
          offset: int = 0,
          limit: int = 50,
      ) -> Sequence[tuple[Event, int]]:
          """Список событий для админ-таблицы с количеством прогнозов.

          Один SQL: LEFT JOIN prediction + GROUP BY event.id + COUNT.
          Фильтры status (`all/draft/published/archived`) и period (`all/next7/past`)
          применяются через WHERE.
          """
          from datetime import UTC, datetime, timedelta
          from ..models import Prediction

          stmt = (
              select(Event, func.count(Prediction.id))
              .outerjoin(Prediction, Prediction.event_id == Event.id)
              .group_by(Event.id)
              .order_by(Event.starts_at.desc(), Event.id.desc())
          )

          stmt = stmt.where(*self._admin_filters(category_id, status))

          now = datetime.now(tz=UTC)
          if period == "next7":
              stmt = stmt.where(Event.starts_at >= now, Event.starts_at < now + timedelta(days=7))
          elif period == "past":
              stmt = stmt.where(Event.starts_at < now)
          # "all" — no extra filter

          stmt = stmt.offset(offset).limit(limit)
          result = await self._session.execute(stmt)
          return [(row[0], int(row[1])) for row in result.all()]

      async def count_for_admin_with_period(
          self,
          *,
          category_id: int | None = None,
          status: AdminEventStatus = "all",
          period: AdminEventPeriod = "all",
      ) -> int:
          """Count с теми же фильтрами, что list_for_admin_with_predictions_count — для пагинации."""
          # ... аналогично, без GROUP BY, через func.count
  ```
  - `AdminEventPeriod` — новый Literal type в том же файле.
  - **`_admin_filters` уже существует** (TASK-007). Переиспользовать.
  - Default `limit=50` — больше категорий, нужно для админ-списка.

### Step 2 — `EventService.list_admin_with_counts`

- [ ] **В `src/shared/services/event.py`** добавить обёртку:
  ```python
  from ..repositories.event import AdminEventPeriod, AdminEventStatus


  class EventService:
      # ... existing methods

      async def list_admin_with_counts(
          self,
          *,
          category_id: int | None = None,
          status: AdminEventStatus = "all",
          period: AdminEventPeriod = "all",
          offset: int = 0,
          limit: int = 50,
      ) -> Sequence[tuple[Event, int]]:
          return await self._events.list_for_admin_with_predictions_count(
              category_id=category_id, status=status, period=period,
              offset=offset, limit=limit,
          )

      async def count_admin(
          self,
          *,
          category_id: int | None = None,
          status: AdminEventStatus = "all",
          period: AdminEventPeriod = "all",
      ) -> int:
          return await self._events.count_for_admin_with_period(
              category_id=category_id, status=status, period=period,
          )
  ```

### Step 3 — Доменные исключения (если новые нужны)

- [ ] Проверь `src/shared/exceptions.py`: уже есть `EventNotFoundError`, `EventNotEnoughOutcomesError`, `EventAlreadyHasResultError`. **Возможно нужен `EventInvalidDatesError`** для случая `predictions_close_at > starts_at` (нарушение CHECK `ck_event_close_before_start` из 0001_init). Сейчас при `IntegrityError` падает сырое исключение.
- [ ] **Если решишь добавить** `EventInvalidDatesError` — обработать `IntegrityError` в `EventService.create_event` / `update_event` через попытку catch и mapping на `predictions_close_at > starts_at`. Опционально на этой итерации — можно оставить ошибку 500 и поправить в следующий раз.

### Step 4 — Routes в `src/admin/routes/events.py`

- [ ] **Новый файл:**
  ```python
  """Routes CRUD событий админки (TASK-022). Вкладка «Данные»; Исходы/Результат — TASK-023/024."""

  from __future__ import annotations

  import json
  from datetime import datetime
  from typing import Any

  from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
  from fastapi.responses import HTMLResponse, RedirectResponse
  from fastapi_csrf_protect import CsrfProtect
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.db import SessionLocal
  from src.shared.exceptions import EventNotEnoughOutcomesError, EventNotFoundError
  from src.shared.models import AdminUser
  from src.shared.repositories.event import AdminEventPeriod, AdminEventStatus
  from src.shared.services import CategoryService, EventService

  from ..app import templates
  from ..deps import current_admin

  __all__ = ["router"]

  router = APIRouter(prefix="/events", tags=["events"])

  PAGE_SIZE = 50  # admin-стол — больше, чем в боте


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  @router.get("", response_class=HTMLResponse)
  async def list_events(
      request: Request,
      category_id: int | None = Query(None),
      status: AdminEventStatus = Query("all"),
      period: AdminEventPeriod = Query("all"),
      page: int = Query(0, ge=0),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      event_service = EventService(session)
      rows = await event_service.list_admin_with_counts(
          category_id=category_id, status=status, period=period,
          offset=page * PAGE_SIZE, limit=PAGE_SIZE,
      )
      total = await event_service.count_admin(category_id=category_id, status=status, period=period)
      categories = await CategoryService(session).list_all_with_counts(include_inactive=True)

      return templates.TemplateResponse(
          request=request,
          name="events/list.html",
          context={
              "admin": admin, "rows": rows, "total": total, "page": page,
              "categories": [c for c, _ in categories],
              "selected_category_id": category_id,
              "selected_status": status, "selected_period": period,
              "page_size": PAGE_SIZE,
          },
      )


  @router.get("/new", response_class=HTMLResponse)
  async def new_form(
      request: Request,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      categories = [c for c, _ in await CategoryService(session).list_all_with_counts(include_inactive=False)]
      return templates.TemplateResponse(
          request=request, name="events/form.html",
          context={
              "admin": admin, "event": None, "categories": categories,
              "form_action": "/events", "error": None, "active_tab": "data",
          },
      )


  @router.post("", response_class=HTMLResponse)
  async def create_event(
      request: Request,
      title: str = Form(...),
      description: str = Form(""),
      category_id: int = Form(...),
      starts_at: str = Form(...),  # ISO datetime string from datetime-local
      predictions_close_at: str = Form(...),
      metadata: str = Form("{}"),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse | RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          metadata_dict: dict[str, Any] = json.loads(metadata) if metadata.strip() else {}
      except json.JSONDecodeError:
          # Render form back with error
          return _render_form_with_error(...)

      try:
          starts_at_dt = datetime.fromisoformat(starts_at)
          close_at_dt = datetime.fromisoformat(predictions_close_at)
      except ValueError:
          return _render_form_with_error(...)

      event = await EventService(session).create_event(
          category_id=category_id, title=title,
          description=description or None,
          metadata=metadata_dict,
          starts_at=starts_at_dt, predictions_close_at=close_at_dt,
          by_admin_id=admin.id,
      )
      return RedirectResponse(url=f"/events/{event.id}", status_code=status.HTTP_302_FOUND)


  @router.get("/{event_id}", response_class=HTMLResponse)
  async def edit_form(
      request: Request,
      event_id: int,
      tab: str = Query("data"),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      event = await EventService(session).get_event(event_id, with_outcomes=True)
      if event is None:
          raise HTTPException(status_code=404)
      categories = [c for c, _ in await CategoryService(session).list_all_with_counts(include_inactive=True)]
      return templates.TemplateResponse(
          request=request, name="events/form.html",
          context={
              "admin": admin, "event": event, "categories": categories,
              "form_action": f"/events/{event_id}", "error": None, "active_tab": tab,
          },
      )


  @router.post("/{event_id}")
  async def update_event(
      request: Request, event_id: int,
      title: str = Form(...), description: str = Form(""),
      category_id: int = Form(...),
      starts_at: str = Form(...), predictions_close_at: str = Form(...),
      metadata: str = Form("{}"),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      # ... парсинг как в create_event
      await EventService(session).update_event(
          event_id, by_admin_id=admin.id,
          title=title, description=description or None,
          category_id=category_id,
          starts_at=datetime.fromisoformat(starts_at),
          predictions_close_at=datetime.fromisoformat(predictions_close_at),
          metadata_=json.loads(metadata) if metadata.strip() else {},
      )
      return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)


  @router.post("/{event_id}/publish")
  async def publish_event(
      request: Request, event_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await EventService(session).publish_event(event_id, by_admin_id=admin.id)
      except EventNotFoundError:
          raise HTTPException(status_code=404)
      except EventNotEnoughOutcomesError:
          return RedirectResponse(
              url=f"/events/{event_id}?error=not_enough_outcomes",
              status_code=status.HTTP_302_FOUND,
          )
      return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)


  @router.post("/{event_id}/unpublish")
  async def unpublish_event(
      request: Request, event_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await EventService(session).unpublish_event(event_id, by_admin_id=admin.id)
      except EventNotFoundError:
          raise HTTPException(status_code=404)
      return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)
  ```
- [ ] **Подключить в `src/admin/app.py`**: `app.include_router(events_routes.router)`.

### Step 5 — Шаблоны Jinja2

#### `src/admin/templates/events/list.html`

- [ ] Таблица с фильтрами в шапке:
  ```html
  {% extends "base.html" %}
  {% block title %}События — Admin{% endblock %}
  {% block content %}
  <div class="container py-4">
      <div class="d-flex justify-content-between mb-3">
          <h1>События</h1>
          <a href="/events/new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> Создать</a>
      </div>

      <!-- Filters -->
      <form method="get" class="row g-3 mb-4">
          <div class="col-md-3">
              <label class="form-label">Категория</label>
              <select name="category_id" class="form-select">
                  <option value="">— все —</option>
                  {% for cat in categories %}
                  <option value="{{ cat.id }}" {% if cat.id == selected_category_id %}selected{% endif %}>{{ cat.name }}</option>
                  {% endfor %}
              </select>
          </div>
          <div class="col-md-3">
              <label class="form-label">Статус</label>
              <select name="status" class="form-select">
                  <option value="all" {% if selected_status == "all" %}selected{% endif %}>все</option>
                  <option value="draft" {% if selected_status == "draft" %}selected{% endif %}>черновики</option>
                  <option value="published" {% if selected_status == "published" %}selected{% endif %}>опубликованные</option>
                  <option value="archived" {% if selected_status == "archived" %}selected{% endif %}>архивные</option>
              </select>
          </div>
          <div class="col-md-3">
              <label class="form-label">Период</label>
              <select name="period" class="form-select">
                  <option value="all" {% if selected_period == "all" %}selected{% endif %}>все</option>
                  <option value="next7" {% if selected_period == "next7" %}selected{% endif %}>ближайшие 7 дней</option>
                  <option value="past" {% if selected_period == "past" %}selected{% endif %}>прошедшие</option>
              </select>
          </div>
          <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-outline-primary w-100" type="submit">Применить</button>
          </div>
      </form>

      <table class="table table-hover">
          <thead>
              <tr>
                  <th>#</th><th>Название</th><th>Категория</th>
                  <th>Старт</th><th>Дедлайн</th><th>Статус</th><th>Прогнозов</th><th>Действия</th>
              </tr>
          </thead>
          <tbody>
              {% for event, pred_count in rows %}
              <tr>
                  <td>{{ event.id }}</td>
                  <td><a href="/events/{{ event.id }}">{{ event.title }}</a></td>
                  <td>{{ event.category_id }}</td>  <!-- TODO TASK-022a: подгружать имя категории через selectinload -->
                  <td>{{ event.starts_at.strftime("%d.%m.%Y %H:%M") }}</td>
                  <td>{{ event.predictions_close_at.strftime("%d.%m %H:%M") }}</td>
                  <td>
                      {% if event.is_archived %}<span class="badge bg-info">архив</span>
                      {% elif not event.is_published %}<span class="badge bg-secondary">черновик</span>
                      {% elif event.predictions_close_at > now %}<span class="badge bg-success">приём открыт</span>
                      {% else %}<span class="badge bg-warning text-dark">приём закрыт</span>
                      {% endif %}
                  </td>
                  <td>{{ pred_count }}</td>
                  <td><a href="/events/{{ event.id }}" class="btn btn-sm btn-outline-secondary">Открыть</a></td>
              </tr>
              {% endfor %}
          </tbody>
      </table>

      <!-- Pagination -->
      {% if total > page_size %}
      <nav>
          <ul class="pagination">
              {% if page > 0 %}
              <li class="page-item"><a class="page-link" href="?page={{ page - 1 }}&...">‹</a></li>
              {% endif %}
              <li class="page-item active"><span class="page-link">{{ page + 1 }}</span></li>
              {% if (page + 1) * page_size < total %}
              <li class="page-item"><a class="page-link" href="?page={{ page + 1 }}&...">›</a></li>
              {% endif %}
          </ul>
      </nav>
      {% endif %}
  </div>
  {% endblock %}
  ```
  - **`now`** — нужен в context для расчёта status. Передавай через handler или Jinja2 context_processor (`templates.env.globals["now"] = lambda: datetime.now(tz=UTC)`).
  - **TODO `category_id` → имя**: для MVP можно показать ID, или подгружать имена batch-методом. Если хочется красиво — `joinedload(Category)` в repo-методе. Полезно сделать сразу — небольшое расширение.

#### `src/admin/templates/events/form.html`

- [ ] Шаблон с **Bootstrap nav-tabs**:
  ```html
  {% extends "base.html" %}
  {% block content %}
  <div class="container py-4">
      <h1>
          {% if event %}{{ event.title }}{% else %}Новое событие{% endif %}
      </h1>

      {% if request.query_params.get("error") == "not_enough_outcomes" %}
      <div class="alert alert-warning">
          Нельзя опубликовать: нужно минимум 2 исхода. Перейдите на вкладку «Исходы».
      </div>
      {% endif %}
      {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}

      <!-- Nav tabs -->
      {% if event %}
      <ul class="nav nav-tabs mb-4">
          <li class="nav-item">
              <a class="nav-link {% if active_tab == 'data' %}active{% endif %}" href="/events/{{ event.id }}?tab=data">Данные</a>
          </li>
          <li class="nav-item">
              <a class="nav-link disabled" href="#">Исходы (TASK-023)</a>
          </li>
          <li class="nav-item">
              <a class="nav-link disabled" href="#">Результат (TASK-024)</a>
          </li>
      </ul>
      {% endif %}

      <!-- Tab content: Data -->
      {% if active_tab == 'data' or not event %}
      <form method="post" action="{{ form_action }}">
          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
          <div class="row g-3">
              <div class="col-md-8">
                  <label class="form-label">Название</label>
                  <input type="text" name="title" class="form-control" required value="{{ event.title if event else '' }}">
              </div>
              <div class="col-md-4">
                  <label class="form-label">Категория</label>
                  <select name="category_id" class="form-select" required>
                      {% for cat in categories %}
                      <option value="{{ cat.id }}" {% if event and event.category_id == cat.id %}selected{% endif %}>{{ cat.name }}</option>
                      {% endfor %}
                  </select>
              </div>
              <div class="col-12">
                  <label class="form-label">Описание</label>
                  <textarea name="description" rows="3" class="form-control">{{ event.description if event else '' }}</textarea>
              </div>
              <div class="col-md-6">
                  <label class="form-label">Старт</label>
                  <input type="datetime-local" name="starts_at" class="form-control" required
                         value="{{ event.starts_at.strftime('%Y-%m-%dT%H:%M') if event else '' }}">
              </div>
              <div class="col-md-6">
                  <label class="form-label">Дедлайн приёма прогнозов</label>
                  <input type="datetime-local" name="predictions_close_at" class="form-control" required
                         value="{{ event.predictions_close_at.strftime('%Y-%m-%dT%H:%M') if event else '' }}">
              </div>
              <div class="col-12">
                  <label class="form-label">Metadata (JSON)</label>
                  <textarea name="metadata" rows="4" class="form-control font-monospace">{{ event.metadata_ | tojson(indent=2) if event else '{}' }}</textarea>
              </div>
          </div>
          <div class="mt-3">
              <button type="submit" class="btn btn-primary">Сохранить</button>
              <a href="/events" class="btn btn-outline-secondary">Отмена</a>
          </div>
      </form>

      <!-- Publish / Unpublish actions -->
      {% if event %}
      <hr class="my-4">
      <div class="d-flex gap-2">
          {% if event.is_archived %}
          <span class="text-muted">Событие архивно. Восстановление вне scope MVP.</span>
          {% elif event.is_published %}
          <form method="post" action="/events/{{ event.id }}/unpublish">
              <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
              <button type="submit" class="btn btn-outline-warning">Снять с публикации</button>
          </form>
          {% else %}
          <form method="post" action="/events/{{ event.id }}/publish">
              <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
              <button type="submit" class="btn btn-success">Опубликовать</button>
          </form>
          {% endif %}
      </div>
      {% endif %}
      {% endif %}
  </div>
  {% endblock %}
  ```

#### `src/admin/templates/base.html` — sidebar

- [ ] Обновить ссылку на События: убрать `disabled`, активная ссылка `/events`. Заглушки оставить на «Пользователи», «Аудит».

### Step 6 — Тесты

#### `tests/integration/services/test_event_service_admin.py` (новый)

5-6 integration через nested_session:

- [ ] `test_list_admin_with_counts_returns_predictions_count` — создать event + 3 prediction → возвращает `(event, 3)`.
- [ ] `test_list_admin_with_counts_filter_by_category`.
- [ ] `test_list_admin_with_counts_filter_status_draft`.
- [ ] `test_list_admin_with_counts_filter_status_published`.
- [ ] `test_list_admin_with_counts_filter_period_next7`.
- [ ] `test_list_admin_with_counts_filter_period_past`.

#### `tests/unit/admin/test_events_handler.py` (новый)

8-10 unit через TestClient (patch SessionLocal в middleware + override current_admin):

- [ ] `test_unauthorized_redirects_to_login`.
- [ ] `test_list_events_renders_with_filters`.
- [ ] `test_new_form_renders_with_categories`.
- [ ] `test_create_event_redirects_to_edit`.
- [ ] `test_create_event_invalid_json_metadata_renders_error` (опционально, если реализована обработка).
- [ ] `test_edit_form_renders_with_tabs`.
- [ ] `test_publish_event_success_redirects`.
- [ ] `test_publish_event_not_enough_outcomes_redirects_with_error_param`.
- [ ] `test_unpublish_event_success_redirects`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая ~9 новых.
- [ ] `uv run pytest tests/integration -m integration` — все integration, включая ~6 новых.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - Логин → / → sidebar показывает «Вошли как: admin».
  - / → logout-кнопка работает (CSRF middleware → 200).
  - /events → пустой список + фильтры в шапке.
  - /events/new → форма с категориями → submit → редирект на /events/{id}.
  - /events/{id} → edit-форма с табами (Данные active, Исходы/Результат disabled).
  - Publish с <2 исходами → редирект `?error=not_enough_outcomes` + alert.
  - Создать 2 исхода (через `psql` — TASK-023 ещё нет UI) → publish работает.
- [ ] Ветка `feature/TASK-022-admin-events`, Conventional Commits:
  - `feat(admin): CsrfTokenMiddleware (request.state.csrf_token DRY)`
  - `feat(admin): admin info in sidebar + universal admin in template context`
  - `feat(repositories): EventRepository.list_for_admin_with_predictions_count + count_for_admin_with_period + AdminEventPeriod`
  - `feat(services): EventService.list_admin_with_counts + count_admin`
  - `feat(admin): events routes (list/new/create/edit/update/publish/unpublish)`
  - `feat(admin): events/list.html + events/form.html with nav-tabs`
  - `chore(admin): шаблоны переписаны на request.state.csrf_token`
  - `test(integration): EventService admin filters (6)`
  - `test(admin): events handler tests (~9)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-022-report.md`, задача → `handoff/archive/TASK-022-admin-events/task.md`.

## Артефакты

```
* src/admin/auth/middleware.py                       # +CsrfTokenMiddleware
* src/admin/app.py                                   # + middleware order + events router
* src/admin/routes/login.py                          # убираем ручную генерацию CSRF в GET /login
* src/admin/routes/categories.py                     # убираем ручную генерацию CSRF в GET-handler'ах
* src/admin/templates/base.html                      # admin-info в sidebar + Events ссылка active
* src/admin/templates/login.html                     # csrf_token через request.state
* src/admin/templates/categories/list.html           # csrf_token через request.state
* src/admin/templates/categories/form.html           # csrf_token через request.state
* src/shared/repositories/event.py                   # +list_for_admin_with_predictions_count + count_for_admin_with_period + AdminEventPeriod
* src/shared/services/event.py                       # +list_admin_with_counts + count_admin
+ src/admin/routes/events.py                         # 7 handlers
+ src/admin/templates/events/list.html               # таблица + фильтры + пагинация
+ src/admin/templates/events/form.html               # форма + nav-tabs + publish/unpublish
+ tests/integration/services/test_event_service_admin.py
+ tests/unit/admin/test_events_handler.py
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — раздел «События»
- [docs/03-data-model.md](../../docs/03-data-model.md) — `Event` + инварианты
- [src/shared/services/event.py](../../src/shared/services/event.py) — `create_event`, `publish_event`, `unpublish_event`, `list_for_admin` уже есть
- [src/admin/routes/categories.py](../../src/admin/routes/categories.py) (TASK-021) — образец CRUD-handler'а

## Подсказки исполнителю

- **`Event.metadata_`** (поле модели) vs **`metadata` (форма)** — поле в модели называется `metadata_` (потому что `metadata` reserved у SQLAlchemy). В сервис передаётся как параметр `metadata`. В шаблоне используется `event.metadata_`.
- **`datetime-local` input в HTML** — возвращает строку `"2026-05-24T15:30"` без timezone. `datetime.fromisoformat(...)` парсит. Если timezone нужен — добавляй `UTC` явно: `dt.replace(tzinfo=UTC)`. На MVP можно оставить naive — модели принимают `timestamptz`, БД сама добавит UTC.
- **`json.loads("")` падает.** Используй `metadata.strip() and json.loads(metadata) or {}` или явный if. Также `JSONDecodeError` ловить и возвращать форму с ошибкой.
- **`now` в шаблоне для status-badges**: добавь `templates.env.globals["now"] = lambda: datetime.now(tz=UTC)` в `app.py` (там же, где другие globals).
- **Middleware-порядок** в FastAPI: `add_middleware` добавляет в **обратном порядке выполнения**. Чтобы `RequireAdminMiddleware` отработал ПЕРВЫМ, добавлять `CsrfTokenMiddleware` **сначала**, потом `RequireAdminMiddleware`. Запутанно — проверяй порядок при отладке.
- **`set_csrf_cookie` через прямую вставку Set-Cookie** в middleware — потому что у нас нет `Response` объекта в чистом ASGI-middleware. См. образец в `RequireAdminMiddleware.send_with_cookie` из TASK-020.
- **`CsrfProtect().generate_csrf_tokens()` — статический метод?** В fastapi-csrf-protect 1.0.7 — это instance метод, нужно создать `CsrfProtect()` (lazy fetch конфига через `@CsrfProtect.load_config`). Если ругается на отсутствие конфига — config должен быть `load_config`'нут в `lifespan` или import-time.
- **Категория имя в events/list.html**: на MVP можно показать `event.category_id` (число). Чище — расширить repo-метод на `joinedload(Event.category)`, но это +1 LEFT JOIN. Если будет шумно — отдельной мелкой задачей или сразу здесь.

## Что НЕ делать

- **Не делать вкладки «Исходы» и «Результат» реально** — только заглушка-disabled-link. Это TASK-023 и TASK-024.
- **Не делать перезапись итога** (`set_result` reset) — спека явно говорит «переопределение итога не предусмотрено в MVP».
- **Не делать flush-сообщения через session** — продолжаем query-string подход.
- **Не делать pagination через HTMX** — обычный server-render.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
