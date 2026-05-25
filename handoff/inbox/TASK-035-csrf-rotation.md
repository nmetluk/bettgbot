---
id: TASK-035
created: 2026-05-25
author: external-auditor
parallel-safe: false
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: M
---

# TASK-035: CSRF rotation на HTMX POST-handler'ах и login

## Контекст

Аудит MVP 2026-05-25, находка **C-03 (Critical, CWE-352)**. `CsrfTokenMiddleware` (`src/admin/auth/middleware.py:149`) генерирует CSRF-токен только для GET-запросов. HTMX-handler'ы outcomes (`src/admin/routes/outcomes.py`) возвращают рендеренные fragment'ы прямо из POST — `_list_response` без перегенерации токена, шаблон читает `{{ request.state.csrf_token }}` (пустой). Дальнейший HTMX POST шлёт пустой токен в body, валидируется против всё ещё валидной cookie. Cookie не ротируется при login, не имеет TTL короче 8 часов session — окно атаки 8 часов, shareable между админами на одном host.

Паттерн правильной обработки уже есть в `_render_login_error` (`src/admin/routes/login.py:35-52`) и `_render_form` (`categories.py:34-60`) — `generate_csrf_tokens()` + `set_csrf_cookie()`. Надо унифицировать.

## Цель

После каждого write-handler'а админки (POST/PUT/PATCH/DELETE), который возвращает HTML/HTMX-fragment с формой/кнопкой делайт — **regenerate CSRF token + reset cookie**. После `POST /login` (успех) — перевыпускать CSRF-cookie заодно с session.

## Definition of Done

- [ ] `src/admin/_helpers.py` (новый файл) экспортирует helper `set_csrf_response_cookie(response, csrf_protect, request) -> tuple[str, Response]`, унифицирующий три существующих `_render_*_error` / `_render_form`.
- [ ] Все handler'ы в `src/admin/routes/outcomes.py`, которые возвращают `_list_response` или `_form` fragment, регенерируют CSRF-токен через helper и пишут cookie.
- [ ] То же для `categories.py` (`_render_form`), `events.py` (где возвращается re-rendered form), `audit.py` (если применимо).
- [ ] `POST /login` (`src/admin/routes/login.py`) при успехе ставит fresh CSRF-cookie через `csrf_protect.set_csrf_cookie(...)` на `RedirectResponse`.
- [ ] `Settings` определяет `admin.session_samesite: Literal["lax","strict"] = "strict"` (default для admin-only UI); cookies (session + csrf) ставятся с этим значением. Dev может переопределить.
- [ ] Cookies named with `__Host-` prefix в prod (`__Host-bb_admin_session`, `__Host-fastapi-csrf-token`) — браузер enforce'ит `Path=/`, `Secure`, без `Domain`. Условно по `environment != "dev"`.
- [ ] Unit-тест: HTMX POST `/events/{id}/outcomes/{outcome_id}` возвращает response с Set-Cookie `fastapi-csrf-token=<new-value>`, отличающейся от cookie во входящем запросе.
- [ ] Unit-тест: `POST /login` (success) выставляет **обе** cookies (session + новый csrf-token).
- [ ] PR в GitHub, имя `TASK-035: rotate CSRF token on HTMX POST and login`.
- [ ] Отчёт в `handoff/outbox/TASK-035-report.md`.
- [ ] **🚨 Move-семантика inbox→archive** (см. handoff/README.md).
- [ ] **🚨 `make backup` после merge в main**.

## Артефакты

- `+ src/admin/_helpers.py` — новый, общий CSRF-cookie helper
- `* src/admin/routes/outcomes.py` — все 5 write-handler'ов
- `* src/admin/routes/categories.py` — заменить inline `_render_form` на helper
- `* src/admin/routes/events.py` — re-rendered form на ошибку
- `* src/admin/routes/login.py` — fresh CSRF на login success
- `* src/admin/auth/middleware.py` — `__Host-` prefix conditional
- `* src/shared/config.py` — `admin.session_samesite`
- `* tests/unit/admin/test_outcomes_handler.py` — Set-Cookie проверка
- `* tests/unit/admin/test_login_handler.py` — двойная Set-Cookie

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-03
- DECISIONS 2026-05-24 «CSRF token доступен везде через `request.state.csrf_token`»

## Подсказки

- `__Host-` cookies могут сломать тесты, которые проверяют конкретное имя cookie — обновить тестовые константы.
- При SameSite=Strict логин-форма из e-mail-ссылки не работает (не применяется в проекте, но иметь в виду).
- `fastapi-csrf-protect` API: `csrf_protect.generate_csrf_tokens() -> tuple[token, signed]`, `csrf_protect.set_csrf_cookie(signed, response)`.
- Не забывай: helper должен принимать `request` для записи `request.state.csrf_token` (иначе шаблон не увидит).
