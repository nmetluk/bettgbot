---
id: TASK-037
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: M
---

# TASK-037: Security headers middleware (CSP, X-Frame, Permissions-Policy) + SRI на CDN

## Контекст

Аудит MVP 2026-05-25, находки **C-05 + H-19 + H-21**. FastAPI не выставляет CSP/X-Frame/Permissions-Policy. Nginx даёт только HSTS+X-Frame+nosniff, причём HSTS без `includeSubDomains; preload`. Bootstrap 5 и HTMX 2 грузятся с `cdn.jsdelivr.net` без `integrity="sha384-..."` — компрометация jsdelivr = JS execution в админке. JS-context-XSS через `onsubmit="return confirm('... {{ category.name }} ...')"` пробивает Jinja autoescape (HTML-escape недостаточен в JS-string).

## Цель

Добавить layered security headers (app + nginx), убрать JS-attribute-context (`onsubmit`/`hx-confirm` с шаблонными переменными), захэшить или self-host CDN-ассеты.

## Definition of Done

- [ ] `src/admin/_security_headers.py` (новый) — ASGI middleware `SecurityHeadersMiddleware`, выставляет:
  - `Content-Security-Policy: default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: geolocation=(), camera=(), microphone=(), interest-cohort=()`
- [ ] Middleware подключён в `src/admin/app.py:create_app()`.
- [ ] `infra/nginx/admin.conf.template`:
  - HSTS: `max-age=63072000; includeSubDomains; preload`
  - `ssl_ciphers` обновлены на Mozilla Intermediate: `ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384`
  - Добавлены: `ssl_session_tickets off; ssl_stapling on; ssl_stapling_verify on; resolver 1.1.1.1 8.8.8.8 valid=300s; resolver_timeout 5s;`
- [ ] CDN-ассеты в `src/admin/templates/base.html` получили `integrity="sha384-..."` и `crossorigin="anonymous"`. Хэши извлечь из `https://www.srihash.org/` или вручную через `curl URL | openssl dgst -sha384 -binary | openssl base64 -A`.
- [ ] Удалены inline-`onsubmit`/`hx-confirm` со шаблонными переменными:
  - `src/admin/templates/categories/list.html:48` → `<button data-confirm="Удалить категорию «${name}»?" data-name="{{ category.name|e }}" class="js-confirm-delete">`
  - `src/admin/templates/outcomes/_list.html:26` → аналогично
  - `src/admin/static/js/confirm.js` (новый) — делегированный handler читает `data-confirm` + `data-name`, escape через DOM-text, не innerHTML.
- [ ] Unit-тест `tests/unit/admin/test_security_headers.py`: GET `/` возвращает headers (CSP, XFO, nosniff, RP, PP).
- [ ] Integration-тест: создать категорию с `name="A);alert(1);//"` через service → шаблон рендерит безопасно (нет XSS).
- [ ] PR в GitHub, имя `TASK-037: security headers middleware + SRI + remove JS-context interpolation`.
- [ ] Отчёт в `handoff/outbox/TASK-037-report.md`.
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `+ src/admin/_security_headers.py` — middleware
- `* src/admin/app.py` — подключить middleware
- `* infra/nginx/admin.conf.template` — TLS+HSTS
- `* src/admin/templates/base.html` — SRI
- `* src/admin/templates/categories/list.html` — без inline onsubmit
- `* src/admin/templates/outcomes/_list.html` — без hx-confirm со значением
- `+ src/admin/static/js/confirm.js`
- `+ tests/unit/admin/test_security_headers.py`

## Ссылки

- Mozilla SSL Config Generator: https://ssl-config.mozilla.org/#server=nginx&config=intermediate
- CSP cheatsheet: https://content-security-policy.com/
- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — C-05, H-19, H-21

## Подсказки

- CSP `'unsafe-inline'` для style оставить — Bootstrap inline-styles. Для script можно убрать (HTMX и Bootstrap-JS — оба из cdn).
- При тестах с TestClient заголовки придут только при использовании `app` через ASGI, не через раздельный handler-вызов. Тест-кейс должен использовать `TestClient(app)`.
- `confirm.js` — мини-скрипт ~20 строк; держи его inline в шаблоне НЕТ — это противоречит CSP без `'unsafe-inline'` для script. Раздельный файл.
