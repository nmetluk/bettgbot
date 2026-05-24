# Brief — task-021-review

**Дата:** 2026-05-24
**Длительность:** короткая сессия cowork

## Запрос владельца

Прочитать отчёт по TASK-021 и подготовить TASK-022.

## Контекст

Локальный CC закрыл TASK-021 за 5 коммитов (squash `7e967ad`), 60 минут. **Первая бизнес-задача в админке готова.** Все 4 этапа задачи реализованы:

- **Step 0**: `Settings.environment: Literal["dev","staging","prod"] = "dev"` + conditional `Secure` cookie в 3 точках (`routes/login.py`, `auth/middleware.py` send-wrapper, `_get_csrf_config`). **Закрывает open Q2 TASK-020** — на dev `http://localhost:8000` больше нет redirect-петли.
- **Step 1-3**: 3 доменных исключения (`CategorySlugConflictError`, `CategoryHasEventsError`, `CategoryNotFoundError`). `CategoryRepository.list_with_event_counts(include_inactive=True)` — outer join + count без фильтра по published/archived (для админ-FK-RESTRICT-семантики). `CategoryService` CRUD-методы с `AuditLogRepository` + обработка `IntegrityError` → доменные исключения.
- **Step 4-5**: 6 handler'ов в `src/admin/routes/categories.py` (list/new/create/edit/update/delete), шаблоны `categories/list.html` (с alert при `?error=has_events` flash) + `categories/form.html` (shared для new+edit через `{% if category and category.id %}`). Sidebar в `base.html` (Дашборд, Категории, disabled-ссылки на будущие разделы, logout-form). `login.html` через `{% block sidebar %}{% endblock %}` гасит sidebar (pre-auth).
- **Step 6**: 15 новых тестов (8 unit handler + 7 integration service). **287 тестов всего** (185 unit + 102 integration).

PR [#61](https://github.com/nmetluk/bettgbot/pull/61) → squash `7e967ad`. Pre-task cleanup PR [#60](https://github.com/nmetluk/bettgbot/pull/60). Archive [#62](https://github.com/nmetluk/bettgbot/pull/62).

## Что сделано в этой сессии

6 open questions исполнителя — **5 keep + 1 change**:

- **(Q1, change → Step 0 TASK-022)** CSRF для sidebar logout-формы на страницах **без** CSRF в context (`/` dashboard): сейчас `csrf_token=""` → `validate_csrf` 403. Локальный CC предложил 3 варианта:
  - (a) Везде в handler'ах генерировать CSRF — шумно, дублирование.
  - (b) Вынести генерацию в middleware: `request.state.csrf_token` доступен везде, шаблон читает оттуда. **DRY, выбираю.**
  - (c) JS-XHR с CSRF из cookie — overengineering для MVP.

  Закрываю **в Step 0 TASK-022**: новый `CsrfMiddleware` который вставляет `csrf_token` в `request.state` для всех GET-запросов под auth + set_csrf_cookie. Существующие handler'ы перестают сами генерировать CSRF — только используют из state. Перепишу шаблоны на `{{ request.state.csrf_token }}` (или Jinja2 context_processor). Без этого пользователь на dashboard не может logout через sidebar.

- **(Q2, keep)** `/login` без sidebar через `{% block sidebar %}{% endblock %}` — layout c `col-md-9` для main даёт лёгкий offset вправо. Косметика, не критично. Если в будущем понадобится centered — переопределим `{% block content %}` в `login.html` через `col-12 mx-auto`.

- **(Q3, keep)** `include_inactive=True` default в `list_with_event_counts` — фиксируем как convention: **админские list-методы по умолчанию показывают всё**, фильтр в UI поверх. Не путать с пользовательскими (бот) — там по умолчанию active+published.

- **(Q4, keep)** Sidebar disabled-ссылки на TASK-022/025/026 — UX-намёк «roadmap». Когда соответствующая задача закроется, ссылка станет активной. Это паттерн для всего Этапа 3.

- **(Q5, keep)** `flash` через query-string `?error=has_events&category_id=N` — простой, работающий. Альтернатива (signed cookie flash через itsdangerous) — preview-функциональность, не нужна на MVP. Когда будем делать сложные flash (multi-line, нескольких типов на одной странице) — рассмотрим itsdangerous.

- **(Q6, change → тоже Step 0 TASK-022)** «Вошли как: {admin.full_name}» в base.html — минорное UX-улучшение, естественно вписывается в правку sidebar для CSRF middleware. Заодно отрендерим имя админа справа от sidebar.

Обновлены:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-021, новый шаг TASK-022.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 3 новых строки (admin list_with_counts convention, sidebar disabled-roadmap паттерн, CSRF в middleware решение).
- Сформирована задача [`handoff/inbox/TASK-022-admin-events.md`](../../handoff/inbox/TASK-022-admin-events.md). Размер L.

## Следующие шаги

1. Локальный CC берёт **TASK-022** (CRUD событий + Step 0 CSRF middleware). Размер L.
2. TASK-023 — CRUD исходов через HTMX inline-edit.
3. TASK-024 — фиксация итога.
4. TASK-025 — список пользователей + блок/разблок.
5. TASK-026 — UI аудит-лога.
