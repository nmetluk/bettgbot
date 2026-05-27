---
task: TASK-037
status: completed
date: 2026-05-27
commit: b8dafa6
pr: https://github.com/nmetluk/bettgbot/pull/93
---

# TASK-037: Security headers middleware (CSP, X-Frame, Permissions-Policy) + SRI

## Что сделано

### 1. Security headers middleware
**Файл**: `src/admin/_security_headers.py`

Создан ASGI middleware `SecurityHeadersMiddleware`, добавляющий следующие заголовки:
- `Content-Security-Policy`: restricts sources to 'self' and cdn.jsdelivr.net
- `X-Frame-Options: DENY` — prevents clickjacking
- `X-Content-Type-Options: nosniff` — prevents MIME-sniffing
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), camera=(), microphone=(), interest-cohort=()`

Middleware подключён в `src/admin/app.py` как outermost (выполняется последним при обработке response).

### 2. Nginx TLS hardening
**Файл**: `infra/nginx/admin.conf.template`

Обновлён TLS-конфиг:
- HSTS: `max-age=63072000; includeSubDomains; preload`
- SSL cipher suites: Mozilla Intermediate
- `ssl_session_tickets off`
- `ssl_stapling on` с resolver 1.1.1.1 / 8.8.8.8

### 3. SRI для CDN ассетов
**Файл**: `src/admin/templates/base.html`

Добавлены `integrity` и `crossorigin="anonymous"` для:
- Bootstrap 5.3.3 CSS (`sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH`)
- Bootstrap Icons 1.11.3 CSS (`sha384-XGjxtQfXaH2tnPFa9x+ruJTuLE3Aa6LhHSWRr1XeTyhezb4abCG4ccI5AkVDxqC+`)
- HTMX 2.0.4 JS (`sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+`)

### 4. XSS prevention — удаление inline handlers
**Файлы**:
- `src/admin/templates/categories/list.html`
- `src/admin/templates/outcomes/_list.html`
- `src/admin/static/js/confirm.js` (новый)

Удалены `onsubmit` и `hx-confirm` с шаблонными переменными (JS-context XSS risk).
Создан `confirm.js` — делегированный handler, использующий DOM textContent для безопасной
построения сообщения. Шаблоны теперь используют `data-confirm` и `data-name` с Jinja-escape (`|e`).

### 5. Тесты
**Файл**: `tests/unit/admin/test_security_headers.py`

6 unit-тестов для проверки всех security headers. Все проходят.

## Коммиты

- `3f13bd4` — feat: security headers middleware + SRI + remove XSS-risky inline handlers
- `5966cd3` — style: fix ruff formatting in _security_headers.py

## PR

https://github.com/nmetluk/bettgbot/pull/93 — слит через squash в main.

## Diff summary

```
 renamed: handoff/inbox/TASK-037-security-headers-csp.md -> handoff/inbox/TASK-037.in-progress.md
 modified: infra/nginx/admin.conf.template
 new file: src/admin/_security_headers.py
 modified: src/admin/app.py
 new file: src/admin/static/js/confirm.js
 modified: src/admin/templates/base.html
 modified: src/admin/templates/categories/list.html
 modified: src/admin/templates/outcomes/_list.html
 new file: tests/unit/admin/test_security_headers.py
```

## Команды для воспроизведения

```bash
# Запуск тестов
uv run pytest tests/unit/admin/test_security_headers.py -v

# Проверка линтера
uv run ruff check src/admin/_security_headers.py

# Запуск админки (для ручной проверки)
make admin
# Открыть http://localhost:8000 и проверить DevTools -> Network Headers
```

## Что не сделано

Ничего — все пункты DoD выполнены.

## Открытые вопросы

Нет.
