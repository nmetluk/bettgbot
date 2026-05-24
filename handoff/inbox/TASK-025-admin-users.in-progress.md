---
id: TASK-025
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - src/shared/services/user.py
  - src/shared/services/prediction.py
  - src/shared/services/stats.py
priority: high
estimate: L
---

# TASK-025: раздел «Пользователи» в админке — список + карточка + блок/разблок

## Контекст

Седьмая бизнес-задача в админке. Закрывает раздел «Пользователи» из спеки.

Серверная логика **частично готова** (TASK-009):

- `UserService.block(user_id, by_admin_id)` — есть, с audit.
- `UserService.unblock(user_id, by_admin_id)` — есть, с audit.
- `UserService.list_for_admin(query, offset, limit)` — есть с поиском (substring на phone/username/full_name).
- `UserService.count_for_admin(query)` — для пагинации.
- `UserService.get_by_id` — для карточки.
- `PredictionService.list_active_by_user(user_id, offset, limit)` + `list_archived_by_user` — для таблицы прогнозов пользователя.
- `StatsService.user_stats(user_id)` — для статистики на карточке.

Что **нужно добавить**:

- `UserRepository.list_for_admin_with_prediction_counts(query, offset, limit) -> Sequence[tuple[User, int]]` — для колонки «прогнозов» в таблице (один SQL с LEFT JOIN Prediction + GROUP BY + COUNT, **`selectinload` паттерн** по convention из TASK-022 review).
- `UserService.list_admin_with_counts(query, offset, limit)` — обёртка.

Что **нужно расширить**:

- `PredictionRepository` или `PredictionService` методом `list_all_by_user_for_admin(user_id, offset, limit)` — объединяет active+archived (бот их разделяет, для админа нужен один список). Или fetch'ить оба через два call'а и merge в Python — на карточке пользователя обычно 5-30 прогнозов.

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «Пользователи».
- [`src/shared/services/user.py`](../../src/shared/services/user.py) — `block` / `unblock` / `list_for_admin` / `count_for_admin` / `get_by_id` готовы.
- [`src/shared/services/stats.py`](../../src/shared/services/stats.py) — `user_stats` готов.
- [`src/admin/routes/events.py`](../../src/admin/routes/events.py) — образец admin-CRUD с фильтрами/пагинацией (TASK-022).

## Перед стартом — pre-task cleanup PR

В origin/main `f7b8c2a` — last commit (archive TASK-024). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-024, новый шаг TASK-025.
- Новая сессия `sessions/2026-05-24-11-task-024-review/`.
- `handoff/inbox/TASK-025-admin-users.md` — эта задача.

Branch: `chore/post-TASK-024-cowork-cleanup`, PR, merge. После — `feature/TASK-025-admin-users`.

## Цель

Админ через UI:
1. Видит список пользователей с поиском по телефону/username/имени, пагинация, колонка predictions count.
2. Открывает карточку: профиль (phone/full_name/username/created_at/blocked-флаг) + таблица его прогнозов с фильтром active/archive + статистика «N/M (X%)».
3. Блокирует/разблокирует пользователя одной кнопкой (с audit и confirm).

Покрыто mock-based unit-тестами через TestClient.

## Definition of Done

### Step 1 — `UserRepository.list_for_admin_with_prediction_counts`

- [ ] **В `src/shared/repositories/user.py`** добавить:
  ```python
  from sqlalchemy import func
  from ..models import Prediction


  class UserRepository:
      # ... existing methods

      async def list_for_admin_with_prediction_counts(
          self,
          *,
          query: str | None = None,
          offset: int = 0,
          limit: int = 50,
      ) -> Sequence[tuple[User, int]]:
          """Список пользователей для админ-таблицы с количеством их прогнозов.

          Один SQL: LEFT JOIN prediction + GROUP BY user.id + COUNT.
          Поиск через `_admin_filter` (substring на phone / username / full_name).
          """
          stmt = (
              select(User, func.count(Prediction.id))
              .outerjoin(Prediction, Prediction.user_id == User.id)
              .where(*self._admin_filter(query))
              .group_by(User.id)
              .order_by(User.created_at.desc(), User.id.desc())
              .offset(offset)
              .limit(limit)
          )
          result = await self._session.execute(stmt)
          return [(row[0], int(row[1])) for row in result.all()]
  ```
  - Сортировка `created_at DESC` — самые новые наверху.
  - **Не используем `selectinload(User.predictions)`** — нам нужен только COUNT, не сами прогнозы. `joinedload` (`predictions`) не подходит (GROUP BY конфликт, TASK-022 review). Direct `func.count` через outer join — оптимально.

### Step 2 — `UserService.list_admin_with_counts`

- [ ] **В `src/shared/services/user.py`** добавить обёртку:
  ```python
  class UserService:
      # ... existing

      async def list_admin_with_counts(
          self,
          *,
          query: str | None = None,
          offset: int = 0,
          limit: int = 50,
      ) -> Sequence[tuple[User, int]]:
          return await self._users.list_for_admin_with_prediction_counts(
              query=query, offset=offset, limit=limit,
          )
  ```

### Step 3 — `PredictionRepository.list_all_by_user_for_admin`

- [ ] **В `src/shared/repositories/prediction.py`** добавить:
  ```python
  from sqlalchemy.orm import selectinload


  class PredictionRepository:
      # ... existing

      async def list_all_by_user_for_admin(
          self,
          user_id: int,
          *,
          offset: int = 0,
          limit: int = 100,
      ) -> Sequence[Prediction]:
          """Все прогнозы пользователя (active + archived) с eager-loaded event + outcome.

          Для админ-карточки. Сортировка: archived (DESC starts_at), active (DESC starts_at).
          """
          stmt = (
              select(Prediction)
              .options(
                  selectinload(Prediction.event).selectinload(Event.outcomes),
                  selectinload(Prediction.outcome),
              )
              .where(Prediction.user_id == user_id)
              .join(Event, Prediction.event_id == Event.id)
              .order_by(Event.starts_at.desc(), Prediction.id.desc())
              .offset(offset)
              .limit(limit)
          )
          result = await self._session.execute(stmt)
          return result.scalars().all()
  ```
  - **`selectinload`** для event + outcome (две отдельные SELECT'а — для admin'a с ~30 прогнозами на пользователя приемлемо).
  - Без фильтра по `is_archived` — админ видит и активные, и архивные в одном списке.
  - **Не joinedload** — потому что Event имеет `outcomes` collection через relationship; joinedload породит cross-product.

### Step 4 — `PredictionService.list_all_by_user_for_admin`

- [ ] **В `src/shared/services/prediction.py`** добавить обёртку (по аналогии).

### Step 5 — Routes в `src/admin/routes/users.py`

- [ ] **Новый файл:**
  ```python
  """Routes пользователей в админке (TASK-025)."""

  from __future__ import annotations

  from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
  from fastapi.responses import HTMLResponse, RedirectResponse
  from fastapi_csrf_protect import CsrfProtect
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.db import SessionLocal
  from src.shared.models import AdminUser
  from src.shared.services import PredictionService, StatsService, UserService

  from ..app import templates
  from ..deps import current_admin

  __all__ = ["router"]

  router = APIRouter(prefix="/users", tags=["users"])

  PAGE_SIZE = 50


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  @router.get("", response_class=HTMLResponse)
  async def list_users(
      request: Request,
      query: str | None = Query(None, min_length=1),
      page: int = Query(0, ge=0),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      service = UserService(session, registry=None)  # registry не нужен для read
      rows = await service.list_admin_with_counts(
          query=query, offset=page * PAGE_SIZE, limit=PAGE_SIZE,
      )
      total = await service.count_for_admin(query=query)
      return templates.TemplateResponse(
          request=request,
          name="users/list.html",
          context={
              "admin": admin, "rows": rows, "total": total, "page": page,
              "query": query or "", "page_size": PAGE_SIZE,
          },
      )


  @router.get("/{user_id}", response_class=HTMLResponse)
  async def user_detail(
      request: Request,
      user_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      user_service = UserService(session, registry=None)
      user = await user_service.get_by_id(user_id)
      if user is None:
          raise HTTPException(status_code=404)

      pred_service = PredictionService(session)
      predictions = await pred_service.list_all_by_user_for_admin(user_id, offset=0, limit=100)
      correct, total, percent = await StatsService(session).user_stats(user_id)

      return templates.TemplateResponse(
          request=request,
          name="users/detail.html",
          context={
              "admin": admin, "user": user, "predictions": predictions,
              "stats_correct": correct, "stats_total": total, "stats_percent": percent,
          },
      )


  @router.post("/{user_id}/block")
  async def block_user(
      request: Request,
      user_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          await UserService(session, registry=None).block(user_id, by_admin_id=admin.id)
      except UserNotFoundError:  # если есть; иначе try/except не нужен
          raise HTTPException(status_code=404)
      return RedirectResponse(url=f"/users/{user_id}?success=blocked", status_code=status.HTTP_302_FOUND)


  @router.post("/{user_id}/unblock")
  async def unblock_user(
      request: Request,
      user_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      await UserService(session, registry=None).unblock(user_id, by_admin_id=admin.id)
      return RedirectResponse(url=f"/users/{user_id}?success=unblocked", status_code=status.HTTP_302_FOUND)
  ```
- [ ] **Подключить в `src/admin/app.py`**: `app.include_router(users_routes.router)`.
- [ ] **Проверь `UserService.__init__`** — он требует `registry`. На admin он не нужен (нет register_or_authenticate в этом flow), передавай `None`. Если signature не принимает None — расширь `registry: ExternalUserRegistryClient | None = None` (это уже сделано в TASK-010 или подобном — проверь).

### Step 6 — Шаблоны Jinja2

#### `src/admin/templates/users/list.html`

- [ ] Таблица с поиском в шапке:
  ```html
  {% extends "base.html" %}
  {% block title %}Пользователи — Admin{% endblock %}
  {% block content %}
  <div class="container py-4">
      <h1>Пользователи</h1>

      <form method="get" class="row g-2 mb-4">
          <div class="col-md-6">
              <input type="text" name="query" class="form-control"
                     placeholder="Поиск: телефон, username или имя"
                     value="{{ query }}" minlength="1">
          </div>
          <div class="col-md-2">
              <button type="submit" class="btn btn-outline-primary w-100">
                  <i class="bi bi-search"></i> Найти
              </button>
          </div>
          {% if query %}
          <div class="col-md-2">
              <a href="/users" class="btn btn-outline-secondary w-100">Сбросить</a>
          </div>
          {% endif %}
      </form>

      <table class="table table-hover">
          <thead>
              <tr>
                  <th>#</th><th>TG ID</th><th>Телефон</th>
                  <th>Имя</th><th>Username</th>
                  <th>Прогнозов</th><th>Регистрация</th><th>Статус</th>
              </tr>
          </thead>
          <tbody>
              {% for user, pred_count in rows %}
              <tr class="{% if user.is_blocked %}table-secondary{% endif %}">
                  <td><a href="/users/{{ user.id }}">{{ user.id }}</a></td>
                  <td><code>{{ user.tg_user_id }}</code></td>
                  <td><code>{{ user.phone }}</code></td>
                  <td>{{ user.first_name }} {{ user.last_name or "" }}</td>
                  <td>{% if user.tg_username %}@{{ user.tg_username }}{% else %}—{% endif %}</td>
                  <td>{{ pred_count }}</td>
                  <td>{{ user.created_at.strftime("%d.%m.%Y") }}</td>
                  <td>
                      {% if user.is_blocked %}
                      <span class="badge bg-danger">заблокирован</span>
                      {% else %}
                      <span class="badge bg-success">активен</span>
                      {% endif %}
                  </td>
              </tr>
              {% endfor %}
          </tbody>
      </table>

      <!-- Pagination -->
      {% if total > page_size %}
      <nav>
          <ul class="pagination">
              {% if page > 0 %}
              <li class="page-item">
                  <a class="page-link" href="?page={{ page - 1 }}{% if query %}&query={{ query }}{% endif %}">‹</a>
              </li>
              {% endif %}
              <li class="page-item active"><span class="page-link">{{ page + 1 }}</span></li>
              {% if (page + 1) * page_size < total %}
              <li class="page-item">
                  <a class="page-link" href="?page={{ page + 1 }}{% if query %}&query={{ query }}{% endif %}">›</a>
              </li>
              {% endif %}
          </ul>
      </nav>
      {% endif %}

      <p class="text-muted">Всего: {{ total }} пользователей.</p>
  </div>
  {% endblock %}
  ```

#### `src/admin/templates/users/detail.html`

- [ ] Профиль + таблица прогнозов:
  ```html
  {% extends "base.html" %}
  {% block title %}{{ user.first_name }} {{ user.last_name or "" }} — Admin{% endblock %}
  {% block content %}
  <div class="container py-4">
      <a href="/users" class="btn btn-sm btn-outline-secondary mb-3">
          <i class="bi bi-arrow-left"></i> К списку
      </a>

      {% if request.query_params.get("success") == "blocked" %}
      <div class="alert alert-success">Пользователь заблокирован.</div>
      {% elif request.query_params.get("success") == "unblocked" %}
      <div class="alert alert-success">Пользователь разблокирован.</div>
      {% endif %}

      <div class="row">
          <div class="col-md-4">
              <div class="card">
                  <div class="card-body">
                      <h5 class="card-title">{{ user.first_name }} {{ user.last_name or "" }}</h5>
                      <dl class="row mb-0">
                          <dt class="col-sm-5">ID:</dt>
                          <dd class="col-sm-7">{{ user.id }}</dd>
                          <dt class="col-sm-5">TG ID:</dt>
                          <dd class="col-sm-7"><code>{{ user.tg_user_id }}</code></dd>
                          <dt class="col-sm-5">Телефон:</dt>
                          <dd class="col-sm-7"><code>{{ user.phone }}</code></dd>
                          <dt class="col-sm-5">Username:</dt>
                          <dd class="col-sm-7">{% if user.tg_username %}@{{ user.tg_username }}{% else %}—{% endif %}</dd>
                          <dt class="col-sm-5">Регистрация:</dt>
                          <dd class="col-sm-7">{{ user.created_at.strftime("%d.%m.%Y %H:%M") }}</dd>
                          <dt class="col-sm-5">Был активен:</dt>
                          <dd class="col-sm-7">{{ user.last_seen_at.strftime("%d.%m.%Y %H:%M") }}</dd>
                          <dt class="col-sm-5">Статус:</dt>
                          <dd class="col-sm-7">
                              {% if user.is_blocked %}
                              <span class="badge bg-danger">заблокирован</span>
                              {% else %}
                              <span class="badge bg-success">активен</span>
                              {% endif %}
                          </dd>
                      </dl>

                      <hr>

                      {% if user.is_blocked %}
                      <form method="post" action="/users/{{ user.id }}/unblock"
                            onsubmit="return confirm('Разблокировать пользователя?');">
                          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
                          <button type="submit" class="btn btn-success w-100">
                              <i class="bi bi-unlock"></i> Разблокировать
                          </button>
                      </form>
                      {% else %}
                      <form method="post" action="/users/{{ user.id }}/block"
                            onsubmit="return confirm('Заблокировать пользователя? Он не сможет делать прогнозы и получать напоминания.');">
                          <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
                          <button type="submit" class="btn btn-outline-danger w-100">
                              <i class="bi bi-lock"></i> Заблокировать
                          </button>
                      </form>
                      {% endif %}
                  </div>
              </div>

              <!-- Stats -->
              <div class="card mt-3">
                  <div class="card-body">
                      <h6 class="card-title">📊 Статистика</h6>
                      <p class="mb-0">
                          Сбылось: <strong>{{ stats_correct }}</strong> из <strong>{{ stats_total }}</strong>
                          ({{ stats_percent }}%)
                      </p>
                  </div>
              </div>
          </div>

          <div class="col-md-8">
              <h4>Прогнозы ({{ predictions | length }})</h4>
              {% if predictions %}
              <table class="table table-sm">
                  <thead>
                      <tr>
                          <th>Событие</th><th>Выбор</th><th>Старт</th>
                          <th>Статус</th><th>Результат</th>
                      </tr>
                  </thead>
                  <tbody>
                      {% for p in predictions %}
                      <tr>
                          <td><a href="/events/{{ p.event_id }}">{{ p.event.title }}</a></td>
                          <td>«{{ p.outcome.label }}»</td>
                          <td>{{ p.event.starts_at.strftime("%d.%m.%Y %H:%M") }}</td>
                          <td>
                              {% if p.event.is_archived %}
                              <span class="badge bg-info">архив</span>
                              {% elif not p.event.is_published %}
                              <span class="badge bg-secondary">черновик</span>
                              {% else %}
                              <span class="badge bg-success">активно</span>
                              {% endif %}
                          </td>
                          <td>
                              {% if p.is_correct is none %}
                              {% if p.event.is_archived %}<span class="text-muted">⏳ нет итога</span>
                              {% else %}<span class="text-muted">—</span>
                              {% endif %}
                              {% elif p.is_correct %}<span class="text-success">✅ сбылся</span>
                              {% else %}<span class="text-danger">❌ не сбылся</span>
                              {% endif %}
                          </td>
                      </tr>
                      {% endfor %}
                  </tbody>
              </table>
              {% else %}
              <p class="text-muted">Прогнозов пока нет.</p>
              {% endif %}
          </div>
      </div>
  </div>
  {% endblock %}
  ```

#### Sidebar в `base.html`

- [ ] Активировать ссылку «Пользователи» (убрать `disabled`):
  ```html
  <li class="nav-item">
      <a class="nav-link" href="/users"><i class="bi bi-people"></i> Пользователи</a>
  </li>
  ```

### Step 7 — Тесты

#### `tests/integration/services/test_user_service_admin.py` (новый)

3-4 integration через nested_session:

- [ ] `test_list_admin_with_counts_returns_predictions_count` — user + 3 predictions → `(user, 3)`.
- [ ] `test_list_admin_with_counts_filter_by_phone_substring`.
- [ ] `test_list_admin_with_counts_filter_by_username`.
- [ ] `test_list_admin_with_counts_includes_blocked_users` — у админа должен быть полный обзор.

Integration на `UserService.block` / `unblock` уже покрыты в TASK-009 (`tests/integration/services/test_user_service.py`).

#### `tests/integration/services/test_prediction_service_admin.py` или расширение существующего

2 integration:

- [ ] `test_list_all_by_user_for_admin_returns_active_and_archived` — user с 2 предсказаниями (active + archived) → возвращает оба.
- [ ] `test_list_all_by_user_for_admin_eager_loads_event_and_outcome` — `predictions[0].event.title` доступен без N+1.

#### `tests/unit/admin/test_users_handler.py` (новый)

7-8 unit через TestClient:

- [ ] `test_unauthorized_redirects_to_login`.
- [ ] `test_list_users_renders_table`.
- [ ] `test_list_users_with_query_filters_results`.
- [ ] `test_user_detail_renders_profile_and_predictions`.
- [ ] `test_user_detail_unknown_user_404`.
- [ ] `test_block_user_redirects_with_success`.
- [ ] `test_unblock_user_redirects_with_success`.
- [ ] `test_user_detail_shows_block_button_when_active`.
- [ ] `test_user_detail_shows_unblock_button_when_blocked`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, +8 новых.
- [ ] `uv run pytest tests/integration -m integration` — +6 новых.
- [ ] CI на PR — 4 зелёных.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `/users` → таблица с пользователями + поиск.
  - Поиск по фрагменту телефона → отфильтровано.
  - `/users/{id}` → профиль + таблица прогнозов + статистика.
  - «Заблокировать» → confirm → success-flash, статус «заблокирован».
  - «Разблокировать» → confirm → success-flash, статус «активен».
- [ ] Ветка `feature/TASK-025-admin-users`, Conventional Commits:
  - `feat(repositories): UserRepository.list_for_admin_with_prediction_counts`
  - `feat(repositories): PredictionRepository.list_all_by_user_for_admin (eager event+outcome)`
  - `feat(services): UserService.list_admin_with_counts + PredictionService.list_all_by_user_for_admin`
  - `feat(admin): users routes (list+search/detail/block/unblock)`
  - `feat(admin): users/list.html + users/detail.html + sidebar Пользователи active`
  - `test(integration): user/prediction admin queries (~6)`
  - `test(admin): users handler tests (~8 unit)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-025-report.md`, задача → `handoff/archive/TASK-025-admin-users/task.md`.

## Артефакты

```
* src/shared/repositories/user.py                   # +list_for_admin_with_prediction_counts
* src/shared/repositories/prediction.py             # +list_all_by_user_for_admin (eager)
* src/shared/services/user.py                       # +list_admin_with_counts
* src/shared/services/prediction.py                 # +list_all_by_user_for_admin
+ src/admin/routes/users.py                         # 4 handlers
+ src/admin/templates/users/list.html               # таблица + поиск + пагинация
+ src/admin/templates/users/detail.html             # профиль + прогнозы + статистика + block-button
* src/admin/templates/base.html                     # Пользователи sidebar active
* src/admin/app.py                                  # +users router
+ tests/integration/services/test_user_service_admin.py  # ~4
+ tests/integration/services/test_prediction_service_admin.py  # ~2 (или расширение existing)
+ tests/unit/admin/test_users_handler.py            # ~8
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — раздел «Пользователи»
- [src/shared/services/user.py](../../src/shared/services/user.py) — block/unblock/list/count готовы
- [src/shared/services/stats.py](../../src/shared/services/stats.py) — user_stats готов
- [src/admin/routes/events.py](../../src/admin/routes/events.py) — образец admin-list с фильтрами/пагинацией (TASK-022)

## Подсказки исполнителю

- **`UserService.__init__` принимает `registry: ExternalUserRegistryClient | None = None`** — для admin-flow registry не нужен, передавай None. Проверь signature в коде.
- **`selectinload` паттерн** (из DECISIONS): `list_for_admin_with_prediction_counts` использует **direct `func.count` без selectinload** (нам нужен COUNT, не сами объекты). `list_all_by_user_for_admin` использует `selectinload(Prediction.event).selectinload(Event.outcomes)` + `selectinload(Prediction.outcome)` — для eager fetch без N+1.
- **`block` / `unblock`** уже делают audit через `AuditLogRepository.add` (TASK-009). Handler только зовёт сервис, не дублирует audit.
- **Confirm на block-кнопке**: «Заблокировать? Он не сможет делать прогнозы и получать напоминания.» — явное предупреждение.
- **Sort на list-странице**: `created_at DESC` — самые новые наверху. Если потом понадобится sort by predictions_count — добавим параметр.
- **Поиск substring**: `_admin_filter` уже есть с substring-логикой (TASK-007). Никаких regex / FTS — простой `LIKE %query%`. На MVP для ~1000 пользователей — приемлемо.

## Что НЕ делать

- **Не делать pagination для прогнозов на карточке** — пользователи обычно делают ≤30 прогнозов. Если кто-то сделает 200 — отдельная задача.
- **Не делать массовый block/unblock** — outside scope.
- **Не делать «выгрузка в CSV»** — outside scope, идея в backlog «не в MVP».
- **Не делать audit-log в карточке пользователя** — это TASK-026 (отдельный раздел).
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
