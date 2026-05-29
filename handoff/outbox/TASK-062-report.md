# TASK-062: Исправления дефектов админки на проде

## Исполнено

### Дефект №1 — CSRF (блокер)
**Проблема:** На проде `POST /login` всегда возвращал 403. Middleware ставил CSRF-куку как `__Host-fastapi-csrf-token`, а библиотека `fastapi-csrf-protect` читала куку с дефолтным именем `fastapi-csrf-token`.

**Решение:**
- В `src/admin/app.py` в `_csrf_config()` добавлен параметр `cookie_key`, который выбирает правильное имя куки в зависимости от окружения:
  - prod: `CSRF_COOKIE_NAME_PROD` (`__Host-fastapi-csrf-token`)
  - dev: `CSRF_COOKIE_NAME` (`fastapi-csrf-token`)
- Ротация CSRF-куки при успешном логине оставлена (срабатывает и в dev, и в prod)

**Файлы:** `src/admin/app.py`

### Дефект №2 — текст ошибки в шаблоне
**Проблема:** `login.html` выводил захардкоженный «Неверный логин или пароль» для любой ошибки.

**Решение:** Заменён на `{{ error }}` — теперь показывается реальный текст ошибки.

**Файлы:** `src/admin/templates/login.html`

### Дефект №3 — схема статики
**Проблема:** За nginx статика грузилась по `http://` (схема прокси не учитывалась).

**Решение:**
- Добавлен `ProxyHeadersMiddleware` в `create_app()` — теперь `X-Forwarded-Proto` применяется корректно
- Все `url_for('static', ...)` заменены на `/static/...` (root-relative) для defense-in-depth

**Файлы:** `src/admin/app.py`, `src/admin/templates/base.html`, `src/admin/templates/login.html`, `src/admin/templates/_layout_shell.html`, `src/admin/templates/broadcasts/form.html`

### Дефект №4 — мелкие фиксы
- `_login_rate_limit` теперь поднимает `HTTPException(429)` вместо `raise JSONResponse`
- Session-cookie ставится с явным `Path=/` во всех местах (middleware, login, logout)
- `docs/07-deployment.md` исправлен: `/admin` → `/` в шагах проверки

**Файлы:** `src/admin/routes/login.py`, `src/admin/auth/middleware.py`, `docs/07-deployment.md`

## Тесты

Добавлены в `tests/unit/admin/test_login_handler.py`:
- `test_csrf_config_uses_correct_cookie_key` — проверяет логику выбора cookie_key
- `test_login_error_shows_actual_error_text_not_hardcoded` — проверяет что шаблон рендерит {{ error }}
- `test_inactive_account_returns_403_with_disabled_text` — проверяет текст ошибки для отключённого аккаунта
- `test_csrf_error_returns_403_with_session_expired_text` — проверяет текст CSRF-ошибки
- `test_proxy_headers_middleware_applies_x_forwarded_proto` — проверяет что ProxyHeadersMiddleware установлен

Все тесты зелёные (9 passed).

## Проверки

- ✅ `pytest` зелёный
- ✅ `ruff check` чист
- ✅ `mypy src/admin` зелёный
- ⏳ После merge владелец передеплоит web-образ и проверит на `a.pinbetting.ru`:
  - GET `/login` → DevTools видит CSRF-куку с именем `__Host-fastapi-csrf-token` и атрибутами `Secure; Path=/; HttpOnly; SameSite=lax`
  - Логин боевыми креды → редирект на `/`
  - Статика грузится по `https://` с первого запроса

## PR

https://github.com/nmetluk/bettgbot/pull/121

## Коммит

`5db8fd2` — `fix(admin): CSRF cookie mismatch + HTTPS static files (TASK-062)`
