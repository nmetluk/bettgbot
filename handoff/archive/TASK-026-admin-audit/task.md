---
id: TASK-026
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - src/shared/services/audit.py
  - src/shared/repositories/audit_log.py
  - state/BACKLOG.md (тех-долг list_with_admin из TASK-007)
priority: high
estimate: L
---

# TASK-026: UI аудит-лога — финал Этапа 3

## Контекст

**Последняя задача Этапа 3 (веб-админка).** Закрывает «Аудит» из спеки + триггер для отложенного тех-долга «`AuditLogRepository.list_with_admin` с `selectinload`» (TASK-007 review).

Серверная логика **полностью готова** (TASK-009):

- `AuditLogRepository.add` / `list` / `count` с фильтрами (admin_id, action, since, until) + pagination.
- `AuditService.add` / `list` / `count` — обёртки.

Что **нужно сделать в Step 0 (закрытие тех-долга)**: расширить `AuditLogRepository.list` методом eager-loading `selectinload(AuditLog.admin)`, чтобы в шаблоне можно было `entry.admin.full_name` без N+1 SELECT'ов.

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «Аудит»:
  > Таблица: `created_at | admin | action | payload (preview)`. Фильтры: admin, action, диапазон дат. Полный `payload` — раскрытие строки HTMX-фрагментом.
- [`src/shared/services/audit.py`](../../src/shared/services/audit.py) — `list` / `count` / `add` готовы.
- [`src/shared/repositories/audit_log.py`](../../src/shared/repositories/audit_log.py) — расширить `list` под `selectinload(admin)`.
- [`src/admin/routes/outcomes.py`](../../src/admin/routes/outcomes.py) — образец HTMX-handler'ов с `#X-container` + `outerHTML` (TASK-023).
- [`state/BACKLOG.md`](../../state/BACKLOG.md) — тех-долг `list_with_admin`.

## Перед стартом — pre-task cleanup PR

В origin/main `1b15ee9` — last commit (archive TASK-025). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-025, последняя задача Этапа 3 — TASK-026.
- `state/DECISIONS.md` — паттерн `GET /login` для CSRF в тестах.
- Новая сессия `sessions/2026-05-24-12-task-025-review/`.
- `handoff/inbox/TASK-026-admin-audit.md` — эта задача.

Branch: `chore/post-TASK-025-cowork-cleanup`, PR, merge. После — `feature/TASK-026-admin-audit`.

## Цель

Админ через UI видит журнал аудит-записей в таблице, фильтрует по admin/action/датам, раскрывает полный payload без перезагрузки страницы через HTMX. После TASK-026 — **Этап 3 закрыт, 8/8 задач, веб-админка полная**.

## Definition of Done

### Step 0 — Закрытие тех-долга: `AuditLogRepository.list` с `selectinload(admin)`

- [ ] **В `src/shared/repositories/audit_log.py`** обновить `list`:
  ```python
  from sqlalchemy.orm import selectinload
  from ..models import AdminUser  # для type-hint


  async def list(
      self,
      *,
      admin_id: int | None = None,
      action: str | None = None,
      since: datetime | None = None,
      until: datetime | None = None,
      offset: int = 0,
      limit: int = 50,
  ) -> Sequence[AuditLog]:
      stmt = (
          select(AuditLog)
          .options(selectinload(AuditLog.admin))  # NEW: eager-load admin
          .where(*self._filters(admin_id, action, since, until))
          .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
          .offset(offset)
          .limit(limit)
      )
      result = await self._session.execute(stmt)
      return result.scalars().all()
  ```
  - **Удалить из `state/BACKLOG.md`** строку «AuditLogRepository.list_with_admin» — закрыто.
- [ ] Существующие тесты в `tests/integration/services/test_audit_service.py` (если есть) должны продолжать работать. Расширить ассертом `entry.admin.login` (lazy access без N+1).

### Step 1 — `AdminUserRepository.list_all` (для фильтр-dropdown)

- [ ] **Проверь, есть ли `AdminUserRepository`** в `src/shared/repositories/`. Если нет — создать минимальный:
  ```python
  """`AdminUserRepository` — запросы к таблице admin_user."""

  from __future__ import annotations

  from collections.abc import Sequence

  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..models import AdminUser

  __all__ = ["AdminUserRepository"]


  class AdminUserRepository:
      def __init__(self, session: AsyncSession) -> None:
          self._session = session

      async def list_all(self) -> Sequence[AdminUser]:
          result = await self._session.execute(
              select(AdminUser).order_by(AdminUser.login)
          )
          return result.scalars().all()

      async def get_by_id(self, admin_id: int) -> AdminUser | None:
          return await self._session.get(AdminUser, admin_id)
  ```
- [ ] Зарегистрировать в `src/shared/repositories/__init__.py`.
- [ ] **Использовать в admin-handler'е напрямую** для dropdown списка админов (без отдельного service-обёртки — здесь нет бизнес-логики).

### Step 2 — Routes в `src/admin/routes/audit.py`

- [ ] **Новый файл:**
  ```python
  """Routes аудит-лога админки (TASK-026, финал Этапа 3)."""

  from __future__ import annotations

  import json
  from datetime import UTC, datetime

  from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
  from fastapi.responses import HTMLResponse
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.db import SessionLocal
  from src.shared.models import AdminUser
  from src.shared.repositories import AdminUserRepository, AuditLogRepository
  from src.shared.services import AuditService

  from ..app import templates
  from ..deps import current_admin

  __all__ = ["router"]

  router = APIRouter(prefix="/audit", tags=["audit"])

  PAGE_SIZE = 50


  async def _session_dep() -> AsyncSession:
      async with SessionLocal() as session:
          yield session


  def _parse_iso_date(value: str | None) -> datetime | None:
      if not value:
          return None
      try:
          dt = datetime.fromisoformat(value)
          if dt.tzinfo is None:
              dt = dt.replace(tzinfo=UTC)
          return dt
      except ValueError:
          return None


  @router.get("", response_class=HTMLResponse)
  async def list_audit(
      request: Request,
      admin_id: int | None = Query(None),
      action: str | None = Query(None, min_length=1),
      since: str | None = Query(None),
      until: str | None = Query(None),
      page: int = Query(0, ge=0),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      since_dt = _parse_iso_date(since)
      until_dt = _parse_iso_date(until)

      service = AuditService(session)
      rows = await service.list(
          admin_id=admin_id, action=action, since=since_dt, until=until_dt,
          offset=page * PAGE_SIZE, limit=PAGE_SIZE,
      )
      total = await service.count(
          admin_id=admin_id, action=action, since=since_dt, until=until_dt,
      )

      admins = await AdminUserRepository(session).list_all()

      return templates.TemplateResponse(
          request=request, name="audit/list.html",
          context={
              "admin": admin, "rows": rows, "total": total, "page": page,
              "page_size": PAGE_SIZE,
              "admins": admins,  # for dropdown
              "selected_admin_id": admin_id,
              "selected_action": action or "",
              "selected_since": since or "",
              "selected_until": until or "",
          },
      )


  @router.get("/{entry_id}/details", response_class=HTMLResponse)
  async def details_fragment(
      request: Request,
      entry_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      """HTMX-fragment: полный payload одной записи (JSON pretty-print)."""
      entry = await session.get(AuditLog, entry_id)
      if entry is None:
          raise HTTPException(status_code=404)
      return templates.TemplateResponse(
          request=request, name="audit/_details.html",
          context={"entry": entry, "payload_pretty": json.dumps(entry.payload, indent=2, ensure_ascii=False)},
      )
  ```
- [ ] **Импорт `AuditLog`** добавить.
- [ ] **Подключить router в `src/admin/app.py`**: `app.include_router(audit_routes.router)`.

### Step 3 — Шаблоны Jinja2

#### `src/admin/templates/audit/list.html`

```html
{% extends "base.html" %}
{% block title %}Аудит — Admin{% endblock %}
{% block content %}
<div class="container py-4">
    <h1>Журнал аудита</h1>

    <!-- Filters -->
    <form method="get" class="row g-2 mb-4">
        <div class="col-md-3">
            <label class="form-label">Админ</label>
            <select name="admin_id" class="form-select">
                <option value="">— все —</option>
                {% for a in admins %}
                <option value="{{ a.id }}" {% if a.id == selected_admin_id %}selected{% endif %}>
                    {{ a.login }}
                </option>
                {% endfor %}
            </select>
        </div>
        <div class="col-md-2">
            <label class="form-label">Action</label>
            <input type="text" name="action" class="form-control"
                   placeholder="напр. event.create"
                   value="{{ selected_action }}">
        </div>
        <div class="col-md-3">
            <label class="form-label">С (UTC)</label>
            <input type="datetime-local" name="since" class="form-control"
                   value="{{ selected_since }}">
        </div>
        <div class="col-md-3">
            <label class="form-label">По (UTC)</label>
            <input type="datetime-local" name="until" class="form-control"
                   value="{{ selected_until }}">
        </div>
        <div class="col-md-1 d-flex align-items-end">
            <button type="submit" class="btn btn-outline-primary w-100">
                <i class="bi bi-search"></i>
            </button>
        </div>
    </form>

    <table class="table table-hover">
        <thead>
            <tr>
                <th>Когда</th><th>Админ</th><th>Action</th><th>Payload (preview)</th>
            </tr>
        </thead>
        <tbody>
            {% for entry in rows %}
            <tr id="audit-row-{{ entry.id }}">
                <td>
                    <small>{{ entry.created_at.strftime("%d.%m.%Y %H:%M:%S") }}</small>
                </td>
                <td>{{ entry.admin.full_name or entry.admin.login }}</td>
                <td><code>{{ entry.action }}</code></td>
                <td>
                    <div id="audit-details-{{ entry.id }}">
                        <button type="button" class="btn btn-sm btn-outline-secondary"
                                hx-get="/audit/{{ entry.id }}/details"
                                hx-target="#audit-details-{{ entry.id }}"
                                hx-swap="outerHTML">
                            <code style="font-size: 0.85em;">{{ (entry.payload | tojson)[:80] }}{% if (entry.payload | tojson | length) > 80 %}…{% endif %}</code>
                        </button>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    {% if not rows %}
    <p class="text-muted">Записей не найдено.</p>
    {% endif %}

    <!-- Pagination -->
    {% if total > page_size %}
    <nav>
        <ul class="pagination">
            {% set qs = [] %}
            {% if selected_admin_id %}{% set _ = qs.append("admin_id=" ~ selected_admin_id) %}{% endif %}
            {% if selected_action %}{% set _ = qs.append("action=" ~ selected_action) %}{% endif %}
            {% if selected_since %}{% set _ = qs.append("since=" ~ selected_since) %}{% endif %}
            {% if selected_until %}{% set _ = qs.append("until=" ~ selected_until) %}{% endif %}
            {% set qs_extra = ("&" ~ qs | join("&")) if qs else "" %}

            {% if page > 0 %}
            <li class="page-item"><a class="page-link" href="?page={{ page - 1 }}{{ qs_extra }}">‹</a></li>
            {% endif %}
            <li class="page-item active"><span class="page-link">{{ page + 1 }}</span></li>
            {% if (page + 1) * page_size < total %}
            <li class="page-item"><a class="page-link" href="?page={{ page + 1 }}{{ qs_extra }}">›</a></li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}

    <p class="text-muted">Всего записей: {{ total }}.</p>
</div>
{% endblock %}
```

#### `src/admin/templates/audit/_details.html`

```html
{# HTMX-fragment: полный payload одной audit-записи. #}
<div id="audit-details-{{ entry.id }}">
    <pre class="bg-light p-2 mb-1" style="font-size: 0.85em; max-width: 600px; white-space: pre-wrap;"><code>{{ payload_pretty }}</code></pre>
    <button type="button" class="btn btn-sm btn-link"
            hx-get="/audit/{{ entry.id }}/details/collapse"
            hx-target="#audit-details-{{ entry.id }}"
            hx-swap="outerHTML">
        <i class="bi bi-chevron-up"></i> Свернуть
    </button>
</div>
```

- [ ] **Дополнительный handler `GET /audit/{entry_id}/details/collapse`** в `routes/audit.py`:
  ```python
  @router.get("/{entry_id}/details/collapse", response_class=HTMLResponse)
  async def details_collapse(
      request: Request, entry_id: int,
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
  ) -> HTMLResponse:
      """HTMX-fragment: возврат к preview-режиму (collapsed row)."""
      entry = await session.get(AuditLog, entry_id)
      if entry is None:
          raise HTTPException(status_code=404)
      return templates.TemplateResponse(
          request=request, name="audit/_preview.html",
          context={"entry": entry},
      )
  ```
- [ ] **`src/admin/templates/audit/_preview.html`** (для collapse):
  ```html
  {# HTMX-fragment: preview-режим строки (после collapse). #}
  <div id="audit-details-{{ entry.id }}">
      <button type="button" class="btn btn-sm btn-outline-secondary"
              hx-get="/audit/{{ entry.id }}/details"
              hx-target="#audit-details-{{ entry.id }}"
              hx-swap="outerHTML">
          <code style="font-size: 0.85em;">{{ (entry.payload | tojson)[:80] }}{% if (entry.payload | tojson | length) > 80 %}…{% endif %}</code>
      </button>
  </div>
  ```

#### Sidebar в `base.html`

- [ ] Активировать ссылку «Аудит» (убрать `disabled`):
  ```html
  <li class="nav-item">
      <a class="nav-link" href="/audit"><i class="bi bi-journal-text"></i> Аудит</a>
  </li>
  ```

### Step 4 — Тесты

#### `tests/integration/services/test_audit_service.py` — расширить или создать

3-4 теста:

- [ ] `test_list_eager_loads_admin` — создать AdminUser + audit_log, `service.list()[0].admin.login` доступен без отдельного SELECT (проверяется через `selectinload`).
- [ ] `test_list_filter_by_admin_id`.
- [ ] `test_list_filter_by_action_substring` или `equality` (в зависимости от текущей реализации `_filters`).
- [ ] `test_list_filter_by_date_range`.
- [ ] `test_count_matches_list_length`.

#### `tests/unit/admin/test_audit_handler.py` (новый)

6-7 unit через TestClient:

- [ ] `test_unauthorized_redirects_to_login`.
- [ ] `test_list_audit_renders_with_filters`.
- [ ] `test_list_audit_with_admin_id_filter`.
- [ ] `test_list_audit_with_action_filter`.
- [ ] `test_details_fragment_returns_pretty_json`.
- [ ] `test_details_fragment_unknown_id_404`.
- [ ] `test_details_collapse_returns_preview_fragment`.

### Step 5 — Cleanup BACKLOG

- [ ] **Удалить из `state/BACKLOG.md`** строку:
  ```
  - **AuditLogRepository.list_with_admin** с selectinload(admin) — добавить, когда в админке появится UI аудит-лога (TASK-026)...
  ```
  — закрыто в Step 0.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, +6-7 новых.
- [ ] `uv run pytest tests/integration -m integration` — +3-4 новых.
- [ ] CI на PR — 4 зелёных.
- [ ] **Ручная проверка (опц., не в DoD):**
  - `/audit` → таблица с записями audit (после совершения каких-то операций).
  - Фильтр по админу → отфильтровано.
  - Фильтр по action `event.create` → только создания событий.
  - Click на payload-preview → раскрытие полного JSON.
  - Click «Свернуть» → возврат к preview.
- [ ] Ветка `feature/TASK-026-admin-audit`, Conventional Commits:
  - `feat(repositories): AuditLogRepository.list с selectinload(admin); +AdminUserRepository.list_all`
  - `feat(admin): audit routes (list + details fragment + collapse)`
  - `feat(admin): audit/list.html + audit/_details.html + audit/_preview.html + sidebar Аудит active`
  - `test(integration): AuditService eager loading + filters (~4)`
  - `test(admin): audit handler tests (~7 unit)`
  - `docs(backlog): remove AuditLogRepository.list_with_admin (closed in TASK-026)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-026-report.md`, задача → `handoff/archive/TASK-026-admin-audit/task.md`.

## Артефакты

```
* src/shared/repositories/audit_log.py             # +selectinload(admin) в list
+ src/shared/repositories/admin_user.py            # AdminUserRepository (если нет)
* src/shared/repositories/__init__.py              # +AdminUserRepository
+ src/admin/routes/audit.py                        # 3 handlers
+ src/admin/templates/audit/list.html              # таблица + фильтры + пагинация
+ src/admin/templates/audit/_details.html          # HTMX-fragment full payload
+ src/admin/templates/audit/_preview.html          # HTMX-fragment collapse-back
* src/admin/templates/base.html                    # sidebar Аудит active
* src/admin/app.py                                 # +audit router
+ tests/integration/services/test_audit_service.py # ~4 (или расширение)
+ tests/unit/admin/test_audit_handler.py           # ~7
* state/BACKLOG.md                                 # удалить list_with_admin тех-долг
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — раздел «Аудит»
- [src/shared/services/audit.py](../../src/shared/services/audit.py) — готов
- [src/shared/repositories/audit_log.py](../../src/shared/repositories/audit_log.py) — расширить
- [src/admin/routes/outcomes.py](../../src/admin/routes/outcomes.py) — образец HTMX-handler'ов (TASK-023)
- [state/BACKLOG.md](../../state/BACKLOG.md) — тех-долг `list_with_admin`
- [state/DECISIONS.md](../../state/DECISIONS.md) — HTMX-паттерн `#X-container + outerHTML`; `selectinload` при JOIN+GROUP BY; `GET /login` для CSRF в тестах

## Подсказки исполнителю

- **`selectinload(AuditLog.admin)`** — eager-load FK relationship. Это **закрывает тех-долг** из TASK-007 review. Аналогичный паттерн использован в TASK-022 (`Event.category`), TASK-025 (`Prediction.event/outcome`).
- **`datetime-local` input** возвращает naive datetime — `_parse_iso_date` добавляет `UTC` если timezone отсутствует. Это критично для filter'ов, потому что `created_at` хранится в `timestamptz`.
- **HTMX-fragment с per-row `#audit-details-{id}`** — не одно `#X-container` (TASK-023), потому что в таблице много строк. Каждая строка имеет свой контейнер для swap.
- **`payload | tojson` truncated to 80 chars** в Jinja — `(value | tojson)[:80]`. Если payload длиннее 80 байт — добавляем `…`. Простой preview.
- **`json.dumps(payload, indent=2, ensure_ascii=False)`** — pretty-print с поддержкой кириллицы. `ensure_ascii=True` (default) экранирует не-ASCII в `\u00...`.
- **Collapse-route** — отдельный endpoint, который возвращает preview-fragment. Альтернатива (JS-toggle через HTMX events) — сложнее. Сейчас expand+collapse симметричны через два endpoint'а.
- **`AdminUserRepository.list_all()`** не имеет фильтра — на admin-странице обычно ≤5 админов, пагинация излишня. Простой `SELECT ... ORDER BY login`.
- **Filter combinations**: пустые `admin_id` / `action` / `since` / `until` означают «не фильтровать». В шаблоне build query-string с пропуском пустых параметров (или используй `request.url.include_query_params(page=...)` — Starlette helper).

## Что НЕ делать

- **Не делать sort по колонкам** — created_at DESC хардкод.
- **Не делать export в CSV** — outside scope.
- **Не показывать `audit-log` в карточке пользователя** или события — это спека про **общий journal** в отдельном разделе.
- **Не делать realtime через SSE / WebSocket** — page reload или manual refresh достаточно.
- **Не делать «admin filter» через text input** — dropdown из `AdminUser.list_all()` понятнее.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.

## После закрытия — Этап 3 закрыт

После merge'а TASK-026:

- **Этап 3 (веб-админка) — 8/8 задач закрыто.**
- Бот функционально полный (Этап 2) + админка функционально полная (Этап 3).
- Готов для альфа-релиза — admin может создавать события / фиксировать итоги / блокировать пользователей / просматривать audit; пользователи через бот видят события, делают прогнозы, получают напоминания, имеют статистику.
- Дальше — **Этап 4 (production)**: docker-compose override+prod, бэкап, structured logs+ротация, deploy README, smoke-тесты.
