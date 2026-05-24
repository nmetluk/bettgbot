---
task: TASK-026
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/76
branch: feature/TASK-026-admin-audit
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/75 (pre-task cleanup)
commits:
  - 6ca77e8 chore(handoff): take TASK-026 in progress
  - 5f204be feat(repositories): AuditLogRepository.list с selectinload(admin) + AdminUserRepository.list_all; close BACKLOG
  - 70d156d feat(admin): audit routes + list/_details/_preview templates + sidebar Аудит active
  - 17fc808 test: AuditService eager-loading + audit handler tests (1+7)
---

# Отчёт по TASK-026: UI аудит-лога — финал Этапа 3

## Сводка

**Этап 3 (веб-админка) закрыт, 8/8 задач.** Бот функционально полный (Этап 2) + админка функционально полная — готово для альфа-релиза. Дальше Этап 4 (production-deployment).

**Step 0 (закрытие тех-долга):** `AuditLogRepository.list` теперь с `selectinload(AuditLog.admin)`. Удалена строка из `state/BACKLOG.md`. Шаблон обращается к `entry.admin.full_name or entry.admin.login` без N+1 (один SELECT на admins вместо N запросов).

**Step 1:** `AdminUserRepository.list_all()` для filter-dropdown (sort by login). Используется в handler'е напрямую — service-wrapper не нужен, нет бизнес-логики.

**Step 2:** 3 handler'а:
- `GET /audit` — таблица с фильтрами (admin_id, action, since, until через `datetime-local`-input) + pagination.
- `GET /audit/{id}/details` — HTMX-fragment с JSON pretty-print (`json.dumps(indent=2, ensure_ascii=False)`) + кнопка «Свернуть».
- `GET /audit/{id}/details/collapse` — HTMX-fragment возврата в preview.

**Step 3:** 3 шаблона:
- `audit/list.html` — таблица, filter-form, per-row `#audit-details-{id}` контейнер для HTMX.
- `audit/_preview.html` — collapsed-кнопка с payload truncated to 80 chars.
- `audit/_details.html` — expanded `<pre><code>` с pretty JSON + «Свернуть».

`{% include "audit/_preview.html" %}` в list.html — переиспользование шаблона между initial render и collapse-fragment.

Sidebar активирован: «Аудит» теперь работает (была disabled до TASK-026).

**Step 4:** 1 integration на eager-loading (доступ к `entry.admin.login` без lazy IO) + 7 unit handler-тестов (unauthorized → /login, list renders, admin_id filter, action filter, details 200, details 404, collapse возвращает preview).

## Изменённые файлы

```
* src/shared/repositories/audit_log.py            # +selectinload(admin) в list
* src/shared/repositories/admin_user.py           # +list_all() для dropdown
* state/BACKLOG.md                                # -list_with_admin (закрыто)
+ src/admin/routes/audit.py                       # 3 handlers
+ src/admin/templates/audit/list.html             # таблица + фильтры + пагинация
+ src/admin/templates/audit/_preview.html         # HTMX-fragment collapsed
+ src/admin/templates/audit/_details.html         # HTMX-fragment expanded
* src/admin/templates/base.html                   # sidebar Аудит active
* src/admin/app.py                                # +audit router
* tests/integration/services/test_audit_service.py  # +test_list_eager_loads_admin
+ tests/unit/admin/test_audit_handler.py          # 7 unit-тестов
* handoff/inbox/TASK-026-...md → archive/TASK-026-admin-audit/task.md
+ handoff/outbox/TASK-026-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    149 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 75 source files
pytest -m "not integration"      227 passed (было 220; +7 audit handler)
pytest tests/integration         116 passed (было 115; +1 eager loading)

CI PR #76 — все 4 job'а зелёные:
  Lint (ruff)                              9s
  Typecheck (mypy)                         21s
  Tests (pytest, unit)                     20s
  Integration                              51s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
make up && make migrate
make admin.create LOGIN=admin PASSWORD="strong!"
make admin

# Browser flow:
# 1) Сделать какие-то операции (создать категорию, опубликовать событие, и т.д.) — они пишутся в audit.
# 2) /audit → таблица с записями + фильтры.
# 3) Фильтр по action `category.create` → только создания категорий.
# 4) Click на preview-payload → expand с pretty JSON + «Свернуть».
# 5) Click «Свернуть» → возврат в preview.
```

## Что не сделано / вынесено

1. **Sort по колонкам** — спека «created_at DESC хардкод».
2. **Export в CSV** — спека «outside scope».
3. **Realtime через SSE/WebSocket** — спека «outside scope, page reload достаточно».
4. **Audit-log в карточке пользователя/события** — спека «общий journal в отдельном разделе, не per-entity».
5. **`action` filter — exact match** (через `_filters` AuditLogRepository) — substring `LIKE` был бы UX-friendly, но требует расширения `_filters`. Сейчас точное совпадение `action == "event.create"`. Если хотим substring — отдельная мелкая задача.

## Открытые вопросы для проектировщика

1. **`_preview.html` `include` в `list.html`** — переиспользование шаблона. Альтернатива: rendering inline в `list.html`, и отдельный `_preview.html` только для collapse-route. Сейчас DRY через `include` — fragment должен быть один и тот же layout до/после.
2. **Pagination links без HTMX** — обычный `<a href>` с QS-сохранением фильтров. Не HTMX, потому что страница меняется полностью. Если хотим smooth — HTMX boost (`hx-boost="true"` на body). Не в MVP.
3. **`datetime-local` input для since/until — naive datetime** → handler `_parse_iso_date` добавляет UTC. Это значит, что admin вводит UTC-время вручную. Если хотим local TZ → JS-конверсия или server-side с `Settings.timezone`. На MVP — UTC явно в label «(UTC)».
4. **`action` точное совпадение** через `==` в `_filters`. Substring (`ilike`) был бы friendlier для autocompletion. Не критично.
5. **`AdminUserRepository.list_all()` без service-обёртки** — handler зовёт repo напрямую. Согласовано с convention (нет бизнес-логики). Если хотим единый стиль через service — добавить `AdminAuthService.list_admins()` (но имя не подходит, это auth-сервис). Сейчас OK.
6. **`json.dumps(payload, ensure_ascii=False)`** — кириллица как есть, не `\u04...`. Jinja HTML-escape'ит кавычки → `&#34;` в HTML, но pretty-print остается читаемым внутри `<pre><code>`.

## Этап 3 (8 задач) — итог

```
TASK-019  ✅  FastAPI скелет + Volt assets + create_admin script
TASK-020  ✅  auth (bcrypt + signed cookie + middleware + rate-limit + CSRF)
TASK-021  ✅  CRUD категорий + Settings.environment + conditional Secure cookie
TASK-022  ✅  CRUD событий + CsrfTokenMiddleware (DRY csrf_token) + admin info
TASK-023  ✅  CRUD исходов через HTMX (вкладка Исходы)
TASK-024  ✅  фиксация итога (вкладка Результат)
TASK-025  ✅  раздел Пользователи (список + карточка + блок/разблок)
TASK-026  ✅  UI аудит-лога (финал — этот PR)
```

**Code stats после Этапа 3:**
- 75 source files в src/{shared,bot,admin} (typed strict для shared, non-strict для bot+admin)
- 227 unit + 116 integration tests
- 7 admin routes (login, dashboard, categories, events, outcomes, users, audit)
- HTMX 2.x для inline-edit (outcomes), expand/collapse fragments (audit)

**Готово к Этапу 4 (production):**
- docker-compose override для prod (uvicorn + nginx + watchtower)
- Backup pg_dump cron
- Structured logs + rotation
- Deploy README
- Smoke-tests

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-026: UI аудит-лога — **финал Этапа 3 (8/8)**. `AuditLogRepository.list` с `selectinload(admin)` (закрыт тех-долг TASK-007). `AdminUserRepository.list_all` для filter-dropdown. 3 handler'а в `routes/audit.py` (list+filters+pagination, details fragment, collapse fragment). 3 шаблона (`list.html`, `_preview.html` shared, `_details.html`). Sidebar «Аудит» активирован. 8 новых тестов (227 unit + 116 integration). PR [#76](https://github.com/nmetluk/bettgbot/pull/76) → squash `a5132f3`. Pre-task cleanup [#75](https://github.com/nmetluk/bettgbot/pull/75). **Этап 3 закрыт — админка функционально полная.**
```

## Метрики

- Файлов добавлено: 5 (route + 3 шаблона + 1 test + report)
- Файлов изменено: 5 (audit_log repo, admin_user repo, BACKLOG, app, base.html, test_audit_service)
- Тестов добавлено: 8 (всего 227 unit + 116 integration; было 220+115)
- Время на выполнение: ~40 мин (service готов, repo расширение + UI + HTMX expand/collapse)
