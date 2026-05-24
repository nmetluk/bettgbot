---
id: TASK-021
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - docs/03-data-model.md
  - src/shared/services/category.py
  - src/shared/services/event.py
  - src/shared/repositories/category.py
  - src/admin/app.py
priority: high
estimate: L
---

# TASK-021: CRUD категорий в админке + Settings.environment

## Контекст

Первая бизнес-задача в админке. **Step 0** — закрывает open question #2 из TASK-020 review: `Settings.environment` + conditional `Secure=` cookie (без этого dev на `http://localhost` даёт бесконечный redirect на /login). **Step 1-N** — CRUD категорий: список с фильтром, форма создания/редактирования, удаление (FK-RESTRICT при наличии событий).

Серверная логика **частично готова** ([TASK-007](../archive/TASK-007-repositories)): `CategoryRepository.create/update/delete/list/get_by_id/get_by_slug` все есть. `CategoryService` сейчас read-only ([TASK-012](../archive/TASK-012-events-handler)). Нужно расширить write-методами с audit-логированием.

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «Категории», «Шаблон проекта», «Безопасность».
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — `Category(id, name, slug, sort_order, is_active)`, FK `Event.category_id` RESTRICT.
- [`src/shared/services/event.py`](../../src/shared/services/event.py) — образец write-сервиса с `AuditLogRepository.add` + `session.commit()`.
- [`src/shared/repositories/event.py`](../../src/shared/repositories/event.py) `delete_outcome` + `OutcomeInUseError` (TASK-009) — образец обработки IntegrityError от FK RESTRICT.

## Перед стартом — pre-task cleanup PR

В origin/main `dc7f751` — last commit (archive TASK-020). **Working tree этой машины:**

- `state/PROJECT_STATUS.md` — закрытие TASK-020, новый шаг TASK-021.
- `state/DECISIONS.md` — 4 новых строки (timing-attack, /logout public, CSRF methods, lazy session_maker).
- `state/BACKLOG.md` — 1 пункт (fastapi-limiter 0.2 transition).
- Новая сессия `sessions/2026-05-24-07-task-020-review/`.
- `handoff/inbox/TASK-021-admin-categories.md` — эта задача.

Branch: `chore/post-TASK-020-cowork-cleanup`, PR, merge. После — `feature/TASK-021-admin-categories`.

## Цель

Админ через UI может создать/отредактировать/удалить категорию. Список показывает счётчик связанных событий. Удаление пустой — OK, с событиями — 409 с понятным текстом. Все write-операции пишутся в audit-лог. Покрыто mock-based unit-тестами + integration-тестами на сервис. Заодно закрыт `Secure cookie` dev-bug через Settings.environment.

## Definition of Done

### Step 0 — Settings.environment + conditional Secure cookie

- [ ] **В `src/shared/config.py`** добавить:
  ```python
  from typing import Literal

  Environment = Literal["dev", "staging", "prod"]


  class Settings(BaseSettings):
      environment: Environment = "dev"
      # ... existing fields
  ```
  - Default `"dev"` — для удобства локальной разработки.
  - В `.env.example` добавить `ENVIRONMENT=dev` (закомментирован для prod).
- [ ] **В `src/admin/routes/login.py` `login_submit`** заменить `secure=True` на conditional:
  ```python
  s = get_settings()
  response.set_cookie(
      key=SESSION_COOKIE_NAME,
      value=token,
      httponly=True,
      secure=s.environment != "dev",  # ← было True
      samesite="lax",
      expires=expires,
      path="/",
  )
  ```
- [ ] **В `src/admin/auth/middleware.py` send-wrapper** — там собирается Set-Cookie header вручную, нужно убрать `Secure` для dev:
  ```python
  s = get_settings()
  cookie_parts = [
      f"{SESSION_COOKIE_NAME}={new_token}",
      "HttpOnly",
      "SameSite=Lax",
      "Path=/",
      f"Expires={expires.strftime('%a, %d %b %Y %H:%M:%S GMT')}",
  ]
  if s.environment != "dev":
      cookie_parts.append("Secure")
  cookie_header = "; ".join(cookie_parts)
  ```
- [ ] **В `src/admin/app.py` `_get_csrf_config`** — `cookie_secure` тоже:
  ```python
  @CsrfProtect.load_config
  def _get_csrf_config():
      s = get_settings()
      return _CsrfSettings(
          secret_key=s.admin.csrf_secret.get_secret_value(),
          cookie_secure=s.environment != "dev",
          cookie_samesite="lax",
      )
  ```
- [ ] **В `tests/unit/conftest.py`** добавить stub `os.environ["ENVIRONMENT"] = "dev"` (или оставить default из Settings).

### Step 1 — Доменные исключения

- [ ] **В `src/shared/exceptions.py`** добавить:
  ```python
  class CategorySlugConflictError(DomainError):
      """Категория с таким `slug` уже существует."""

      def __init__(self, slug: str) -> None:
          super().__init__(f"category slug {slug!r} already exists")
          self.slug = slug


  class CategoryHasEventsError(DomainError):
      """Удаление категории невозможно — есть связанные события (FK RESTRICT)."""

      def __init__(self, category_id: int) -> None:
          super().__init__(f"category {category_id} has events; cannot delete")
          self.category_id = category_id


  class CategoryNotFoundError(DomainError):
      """Категория не найдена по id."""

      def __init__(self, category_id: int) -> None:
          super().__init__(f"category {category_id} not found")
          self.category_id = category_id
  ```
- [ ] Обнови `__all__`.

### Step 2 — `CategoryRepository.list_with_event_counts`

- [ ] **В `src/shared/repositories/category.py`** добавить:
  ```python
  from sqlalchemy import func

  from ..models import Category, Event


  class CategoryRepository:
      # ... existing methods

      async def list_with_event_counts(
          self, *, include_inactive: bool = True
      ) -> Sequence[tuple[Category, int]]:
          """Возвращает все категории с числом ВСЕХ связанных событий (включая drafts и архивные).

          Для админского списка: счётчик показывает реальное количество строк
          в FK, по которому работает RESTRICT при удалении. Если хочется
          «активных опубликованных» — это `EventService.list_categories_with_counts`
          из TASK-012.
          """
          stmt = (
              select(Category, func.count(Event.id))
              .outerjoin(Event, Event.category_id == Category.id)
              .group_by(Category.id)
              .order_by(Category.sort_order, Category.id)
          )
          if not include_inactive:
              stmt = stmt.where(Category.is_active.is_(True))
          result = await self._session.execute(stmt)
          return [(row[0], int(row[1])) for row in result.all()]
  ```
  - **`include_inactive=True` по умолчанию** — админ видит и неактивные категории. Фильтр в UI поверх этого.

### Step 3 — Расширить `CategoryService` write-методами

- [ ] **В `src/shared/services/category.py`:**
  ```python
  from typing import Any

  from sqlalchemy.exc import IntegrityError

  from ..exceptions import (
      CategoryHasEventsError,
      CategoryNotFoundError,
      CategorySlugConflictError,
  )
  from ..models import Category
  from ..repositories import AuditLogRepository, CategoryRepository


  class CategoryService:
      def __init__(self, session: AsyncSession) -> None:
          self._session = session
          self._categories = CategoryRepository(session)
          self._audit = AuditLogRepository(session)

      # ... existing read-only methods (get_by_id, get_by_slug, list_active)

      async def list_all_with_counts(
          self, *, include_inactive: bool = True
      ) -> Sequence[tuple[Category, int]]:
          return await self._categories.list_with_event_counts(include_inactive=include_inactive)

      async def create_category(
          self,
          *,
          name: str,
          slug: str,
          sort_order: int = 0,
          is_active: bool = True,
          by_admin_id: int,
      ) -> Category:
          try:
              category = await self._categories.create(
                  name=name, slug=slug, sort_order=sort_order, is_active=is_active
              )
              await self._audit.add(
                  admin_id=by_admin_id,
                  action="category.create",
                  payload={
                      "category_id": category.id,
                      "name": name,
                      "slug": slug,
                  },
              )
              await self._session.commit()
              return category
          except IntegrityError as exc:
              raise CategorySlugConflictError(slug) from exc

      async def update_category(
          self,
          category_id: int,
          *,
          by_admin_id: int,
          **fields: Any,
      ) -> None:
          existing = await self._categories.get_by_id(category_id)
          if existing is None:
              raise CategoryNotFoundError(category_id)

          if not fields:
              return  # nothing to update — no-op

          try:
              await self._categories.update(category_id, **fields)
              await self._audit.add(
                  admin_id=by_admin_id,
                  action="category.update",
                  payload={"category_id": category_id, "fields": list(fields.keys())},
              )
              await self._session.commit()
          except IntegrityError as exc:
              raise CategorySlugConflictError(
                  slug=fields.get("slug", existing.slug)
              ) from exc

      async def delete_category(self, category_id: int, *, by_admin_id: int) -> None:
          existing = await self._categories.get_by_id(category_id)
          if existing is None:
              raise CategoryNotFoundError(category_id)

          try:
              await self._categories.delete(category_id)
              await self._audit.add(
                  admin_id=by_admin_id,
                  action="category.delete",
                  payload={"category_id": category_id, "name": existing.name},
              )
              await self._session.commit()
          except IntegrityError as exc:
              raise CategoryHasEventsError(category_id) from exc
  ```
  - Логика идентична `EventService.delete_outcome` (TASK-009) для FK-RESTRICT обработки.
  - **Не делаем rollback** в сервисе — это работа middleware сессии (правило из `docs/08-conventions.md`).

### Step 4 — Routes в `src/admin/routes/categories.py`

- [ ] **Новый файл:**
  ```python
  """Routes CRUD категорий админки (TASK-021)."""

  from __future__ import annotations

  from fastapi import APIRouter, Depends, Form, Request, status
  from fastapi.responses import HTMLResponse, RedirectResponse
  from fastapi_csrf_protect import CsrfProtect
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.db import SessionLocal
  from src.shared.exceptions import (
      CategoryHasEventsError,
      CategoryNotFoundError,
      CategorySlugConflictError,
  )
  from src.shared.models import AdminUser
  from src.shared.services import CategoryService

  from ..app import templates
  from ..deps import current_admin

  __all__ = ["router"]

  router = APIRouter(prefix="/categories", tags=["categories"])


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  @router.get("", response_class=HTMLResponse)
  async def list_categories(
      request: Request,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      service = CategoryService(session)
      rows = await service.list_all_with_counts(include_inactive=True)
      return templates.TemplateResponse(
          request=request,
          name="categories/list.html",
          context={"admin": admin, "rows": rows},
      )


  @router.get("/new", response_class=HTMLResponse)
  async def new_form(
      request: Request,
      admin: AdminUser = Depends(current_admin),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse:
      csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
      response = templates.TemplateResponse(
          request=request,
          name="categories/form.html",
          context={
              "admin": admin,
              "category": None,
              "csrf_token": csrf_token,
              "error": None,
              "form_action": "/categories",
          },
      )
      csrf_protect.set_csrf_cookie(signed_token, response)
      return response


  @router.post("", response_class=HTMLResponse)
  async def create_category(
      request: Request,
      name: str = Form(...),
      slug: str = Form(...),
      sort_order: int = Form(0),
      is_active: bool = Form(False),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse | RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await CategoryService(session).create_category(
              name=name,
              slug=slug,
              sort_order=sort_order,
              is_active=is_active,
              by_admin_id=admin.id,
          )
      except CategorySlugConflictError as exc:
          return templates.TemplateResponse(
              request=request,
              name="categories/form.html",
              context={
                  "admin": admin,
                  "category": {"name": name, "slug": slug, "sort_order": sort_order, "is_active": is_active},
                  "csrf_token": ...,  # перегенерировать
                  "error": f"Категория со slug «{exc.slug}» уже существует.",
                  "form_action": "/categories",
              },
              status_code=status.HTTP_409_CONFLICT,
          )
      return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)


  @router.get("/{category_id}", response_class=HTMLResponse)
  async def edit_form(
      request: Request,
      category_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse:
      category = await CategoryService(session).get_by_id(category_id)
      if category is None:
          raise HTTPException(status_code=404)
      csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
      response = templates.TemplateResponse(
          request=request,
          name="categories/form.html",
          context={
              "admin": admin,
              "category": category,
              "csrf_token": csrf_token,
              "error": None,
              "form_action": f"/categories/{category_id}",
          },
      )
      csrf_protect.set_csrf_cookie(signed_token, response)
      return response


  @router.post("/{category_id}", response_class=HTMLResponse)
  async def update_category(
      request: Request,
      category_id: int,
      name: str = Form(...),
      slug: str = Form(...),
      sort_order: int = Form(0),
      is_active: bool = Form(False),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> HTMLResponse | RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await CategoryService(session).update_category(
              category_id=category_id,
              by_admin_id=admin.id,
              name=name, slug=slug, sort_order=sort_order, is_active=is_active,
          )
      except CategoryNotFoundError:
          raise HTTPException(status_code=404)
      except CategorySlugConflictError as exc:
          # Аналогично create — рендерим форму с ошибкой и 409.
          ...
      return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)


  @router.post("/{category_id}/delete")
  async def delete_category(
      request: Request,
      category_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await CategoryService(session).delete_category(category_id, by_admin_id=admin.id)
      except CategoryNotFoundError:
          raise HTTPException(status_code=404)
      except CategoryHasEventsError:
          # Возвращаем на /categories с flash-сообщением в query (или в session flash — но flash инфра нет).
          return RedirectResponse(
              url=f"/categories?error=has_events&category_id={category_id}",
              status_code=status.HTTP_302_FOUND,
          )
      return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)
  ```
- [ ] **Registered** в `src/admin/app.py`:
  ```python
  from .routes import categories as categories_routes
  app.include_router(categories_routes.router)
  ```

### Step 5 — Шаблоны Jinja2

#### `src/admin/templates/categories/list.html`

- [ ] Таблица с колонками `id | name | slug | active | sort | events_count | actions`:
  ```html
  {% extends "base.html" %}
  {% block title %}Категории — Betting Bot Admin{% endblock %}
  {% block content %}
  <div class="container py-4">
      <div class="d-flex justify-content-between mb-3">
          <h1>Категории</h1>
          <a href="/categories/new" class="btn btn-primary">
              <i class="bi bi-plus-lg"></i> Добавить
          </a>
      </div>
      {% if request.query_params.get("error") == "has_events" %}
      <div class="alert alert-warning">
          Нельзя удалить категорию #{{ request.query_params.get("category_id") }}: на неё есть события.
      </div>
      {% endif %}
      <table class="table table-hover">
          <thead>
              <tr>
                  <th>#</th><th>Название</th><th>Slug</th>
                  <th>Активна</th><th>Сорт.</th><th>Событий</th><th>Действия</th>
              </tr>
          </thead>
          <tbody>
              {% for category, events_count in rows %}
              <tr>
                  <td>{{ category.id }}</td>
                  <td><a href="/categories/{{ category.id }}">{{ category.name }}</a></td>
                  <td><code>{{ category.slug }}</code></td>
                  <td>{% if category.is_active %}<span class="badge bg-success">да</span>{% else %}<span class="badge bg-secondary">нет</span>{% endif %}</td>
                  <td>{{ category.sort_order }}</td>
                  <td>{{ events_count }}</td>
                  <td>
                      <a href="/categories/{{ category.id }}" class="btn btn-sm btn-outline-secondary">Изм.</a>
                      {% if events_count == 0 %}
                      <form method="post" action="/categories/{{ category.id }}/delete" style="display:inline" onsubmit="return confirm('Удалить категорию «{{ category.name }}»?')">
                          <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                          <button type="submit" class="btn btn-sm btn-outline-danger">Удал.</button>
                      </form>
                      {% endif %}
                  </td>
              </tr>
              {% endfor %}
          </tbody>
      </table>
  </div>
  {% endblock %}
  ```
  - **CSRF для delete-button:** требуется передать `csrf_token` в context. Простейший путь — генерировать его в `list_categories` route (см. образец `new_form`). Либо вынести в `_macros.html` (но это в TASK-022+).
  - **Confirm на delete** — JS `confirm(...)` достаточен на MVP. HTMX-modal — позже.

#### `src/admin/templates/categories/form.html`

- [ ] Форма (новая или редактирование):
  ```html
  {% extends "base.html" %}
  {% block title %}{% if category %}Категория «{{ category.name }}»{% else %}Новая категория{% endif %} — Admin{% endblock %}
  {% block content %}
  <div class="container py-4">
      <h1>{% if category %}Редактирование категории{% else %}Новая категория{% endif %}</h1>
      {% if error %}
      <div class="alert alert-danger">{{ error }}</div>
      {% endif %}
      <form method="post" action="{{ form_action }}">
          <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
          <div class="mb-3">
              <label class="form-label">Название</label>
              <input type="text" name="name" class="form-control" required
                     value="{{ category.name if category else '' }}">
          </div>
          <div class="mb-3">
              <label class="form-label">Slug</label>
              <input type="text" name="slug" class="form-control" required
                     pattern="[a-z0-9-]+"
                     value="{{ category.slug if category else '' }}">
              <div class="form-text">Латиница, цифры, дефис.</div>
          </div>
          <div class="mb-3">
              <label class="form-label">Порядок сортировки</label>
              <input type="number" name="sort_order" class="form-control"
                     value="{{ category.sort_order if category else 0 }}">
          </div>
          <div class="form-check mb-3">
              <input type="checkbox" name="is_active" class="form-check-input" id="is_active"
                     {% if category is none or category.is_active %}checked{% endif %}>
              <label class="form-check-label" for="is_active">Активна</label>
          </div>
          <button type="submit" class="btn btn-primary">Сохранить</button>
          <a href="/categories" class="btn btn-outline-secondary">Отмена</a>
      </form>
  </div>
  {% endblock %}
  ```

#### `src/admin/templates/base.html` — sidebar

- [ ] Расширить sidebar:
  ```html
  {% block sidebar %}
  <nav class="sidebar col-md-2 col-lg-2 d-md-block bg-light">
      <ul class="nav flex-column p-3">
          <li class="nav-item">
              <a class="nav-link" href="/"><i class="bi bi-speedometer2"></i> Дашборд</a>
          </li>
          <li class="nav-item">
              <a class="nav-link" href="/categories"><i class="bi bi-folder"></i> Категории</a>
          </li>
          <li class="nav-item">
              <a class="nav-link disabled" href="#"><i class="bi bi-calendar-event"></i> События (TASK-022)</a>
          </li>
          <li class="nav-item">
              <a class="nav-link disabled" href="#"><i class="bi bi-people"></i> Пользователи (TASK-025)</a>
          </li>
          <li class="nav-item">
              <a class="nav-link disabled" href="#"><i class="bi bi-journal-text"></i> Аудит (TASK-026)</a>
          </li>
          <li class="nav-item mt-3">
              <form method="post" action="/logout">
                  <input type="hidden" name="csrf_token" value="{{ csrf_token if csrf_token else '' }}">
                  <button type="submit" class="btn btn-sm btn-outline-secondary w-100">
                      <i class="bi bi-box-arrow-right"></i> Выйти
                  </button>
              </form>
          </li>
      </ul>
  </nav>
  {% endblock %}
  ```
  - **Disabled-ссылки на будущие разделы** — UX-намёк, что они появятся.
  - **`/logout` форма в sidebar** — каждая страница имеет кнопку выхода.

### Step 6 — Тесты

#### `tests/integration/services/test_category_service_crud.py`

5-6 integration-тестов на nested_session:

- [ ] `test_create_category_writes_audit_and_returns_category`
- [ ] `test_create_category_duplicate_slug_raises_conflict`
- [ ] `test_update_category_unknown_id_raises_not_found`
- [ ] `test_update_category_writes_audit`
- [ ] `test_delete_category_empty_succeeds`
- [ ] `test_delete_category_with_events_raises_has_events`
- [ ] `test_list_all_with_counts_returns_zero_for_empty_category`

#### `tests/unit/admin/test_categories_handler.py`

6-8 unit-тестов через TestClient:

- [ ] `test_unauthorized_redirects_to_login` (GET /categories без cookie)
- [ ] `test_list_categories_renders` (mock `current_admin` + `CategoryService.list_all_with_counts`)
- [ ] `test_new_form_renders_with_csrf`
- [ ] `test_create_category_redirects_on_success`
- [ ] `test_create_category_409_on_slug_conflict`
- [ ] `test_edit_form_renders_for_existing_category`
- [ ] `test_delete_category_with_events_redirects_with_error_param`
- [ ] `test_delete_category_empty_redirects_clean`

**Mocks pattern:**
- `monkeypatch.setattr("src.admin.routes.categories.SessionLocal", mock_factory)`.
- `monkeypatch.setattr("src.admin.routes.categories.CategoryService", lambda session: mock_service)`.
- `current_admin` через `app.dependency_overrides[current_admin] = lambda: fake_admin`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая ~7 новых.
- [ ] `uv run pytest tests/integration -m integration` — все integration, включая 6-7 новых на CategoryService.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `make admin.create LOGIN=admin PASSWORD="strong"`
  - `make admin` (теперь в dev cookie без Secure, не будет редирект-петли)
  - Логин → / → дашборд → ссылка «Категории» → пусто.
  - «Добавить» → форма → submit → редирект, в списке появилась.
  - Edit-форма → submit → редирект, обновлено.
  - Создать вторую с тем же slug → 409 + текст.
  - Создать событие в БД с этой категорией → попытка удалить → редирект с error-флагом, alert «нельзя удалить».
- [ ] Ветка `feature/TASK-021-admin-categories`, Conventional Commits:
  - `feat(config): Settings.environment + conditional Secure cookie`
  - `feat(exceptions): Category{SlugConflict,HasEvents,NotFound}Error`
  - `feat(repositories): CategoryRepository.list_with_event_counts`
  - `feat(services): CategoryService CRUD методы + audit`
  - `feat(admin): categories routes (list/new/create/edit/update/delete)`
  - `feat(admin): categories/list.html + categories/form.html + sidebar в base.html`
  - `test(integration): CategoryService CRUD сценарии`
  - `test(admin): categories handler tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-021-report.md`, задача → `handoff/archive/TASK-021-admin-categories/task.md`.

## Артефакты

```
* src/shared/config.py                                  # +Settings.environment
* infra/.env.example                                    # +ENVIRONMENT
* tests/unit/conftest.py                                # +stub ENVIRONMENT (если нужен)
* src/shared/exceptions.py                              # +3 Category*Error
* src/shared/repositories/category.py                   # +list_with_event_counts
* src/shared/services/category.py                       # +CRUD методы + AuditLogRepository
* src/admin/app.py                                      # +categories router; conditional CsrfProtect cookie_secure
* src/admin/auth/middleware.py                          # conditional Secure в send-wrapper
* src/admin/routes/login.py                             # conditional Secure cookie
+ src/admin/routes/categories.py                        # CRUD handlers
+ src/admin/templates/categories/list.html              # таблица + delete-кнопка
+ src/admin/templates/categories/form.html              # форма create/edit
* src/admin/templates/base.html                         # расширен sidebar
+ tests/integration/services/test_category_service_crud.py  # 6-7 тестов
+ tests/unit/admin/test_categories_handler.py           # 6-8 тестов
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — разделы «Категории», «Шаблон проекта»
- [docs/03-data-model.md](../../docs/03-data-model.md) — `Category`, FK `Event.category_id` RESTRICT
- [src/shared/services/event.py](../../src/shared/services/event.py) — образец write-сервиса с audit (`create_event`, `delete_outcome`)
- [src/shared/repositories/category.py](../../src/shared/repositories/category.py) — текущие методы repo
- [src/admin/routes/login.py](../../src/admin/routes/login.py) — образец CSRF + Form-handler
- [state/DECISIONS.md](../../state/DECISIONS.md) — строка про timing-attack mitigation (TASK-020), про /logout public

## Подсказки исполнителю

- **`list_with_event_counts` считает ВСЕ события** (включая archived и drafts) — это для admin-списка, по которому работает FK RESTRICT при delete. Не путать с `EventService.list_categories_with_counts` (TASK-012), которая фильтрует по `is_published AND NOT is_archived` для бота.
- **`IntegrityError` от FK RESTRICT** — стандартный паттерн в SQLAlchemy. Пример обработки — `EventService.delete_outcome` → `OutcomeInUseError` (TASK-009). Та же логика.
- **`AuditLogRepository.add(admin_id, action, payload)`** есть из TASK-007. `action` — точечная строка (`"category.create"`), `payload` — dict с context (без секретов).
- **`Form(False)` для checkbox `is_active`** — HTML-чекбокс отправляет `is_active=on` если включен, **ничего не отправляет** если выключен. FastAPI `Form(False)` ловит это, но **`is_active=False` приведёт к проблеме на uncheck**: при uncheck чекбокс не отправляется, поэтому `is_active=False` будет default. Это OK для checkbox, но проверь, что update сохраняет False (а не игнорирует поле).
- **Sidebar в base.html** — расширяй блок `{% block sidebar %}`. Логин-страница `login.html` не использует sidebar (она не extends с sidebar показом — переопредели `{% block sidebar %}{% endblock %}` если нужно).
- **CSRF на delete-button**: каждая страница, где есть форма с CSRF (включая sidebar logout-form), должна получить `csrf_token` в context. Если макрос для form'ы вынести в `_macros.html` — будет проще. Сейчас минимум: handler генерирует token и передаёт в template.
- **`flash`-messages**: на MVP используем query-string `?error=has_events&category_id=N`, рендеря alert в `list.html`. Полноценный flash (через session) — не нужен.
- **`is_active=False` чекбокс** — раз HTML-чекбокс при uncheck не отправляет ничего, FastAPI Form имеет дефолт. Поэтому в `Form(False)` чекбокс «не активна» приходит как False, «активна» — как True (HTML-параметр `=on` интерпретируется как truthy). Альтернатива — `Form("")` + parse. Но FastAPI с `Form(False)` хорошо обрабатывает это.

## Что НЕ делать

- Не выносить макросы форм в `_macros.html` пока нет повтора — это TASK-022, когда формы появятся для событий и исходов.
- Не делать pagination для списка категорий — их обычно 5-20, влезают.
- Не делать sorting/filtering в UI помимо filter «active/all» — преждевременно. Sort_order сейчас задаётся вручную в форме.
- Не делать перетаскивание (drag-drop sort_order) — это **отдельная задача** после первой обратной связи от админов.
- Не делать flash-messages через session — query-string достаточно для MVP.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
