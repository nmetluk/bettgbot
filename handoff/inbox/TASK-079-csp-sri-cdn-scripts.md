---
id: TASK-079
created: 2026-05-30
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/templates/base.html
  - src/admin/_security_headers.py
  - docs/audit/2026-05-30-design-audit.md
  - docs/audit/2026-05-30-full-audit.md
priority: low
estimate: S
---

# TASK-079: SRI/self-host для CDN-скриптов (D6 / L5 supply-chain)

## Контекст

Дизайн-аудит (D6) и осн. аудит (L5, `_security_headers.py:41`): CSP разрешает
`script-src 'self' https://cdn.jsdelivr.net`. Риск — компрометация/подмена ресурса CDN → исполнение
чужого JS в админке. Низкий приоритет, но единственный непокрытый пункт аудита.

Фактическое состояние (проверено архитектором):
- chart.js@4.4.2 (`analytics/list.html`), bootstrap@5.3.3 CSS и htmx@2.0.4 (`base.html`) — **SRI уже есть**.
- **Alpine.js CSP build** `@alpinejs/csp@3.14.1/dist/cdn.min.js` (`base.html:29`) — **без `integrity`** (дыра).

## Цель

Закрыть supply-chain вектор для CDN-скриптов: либо SRI на всех, либо self-host критичных JS с удалением
CDN из CSP.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-079-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

Выбрать один из путей (рекомендация — self-host, см. ниже), отметить выбор в отчёте:

**Путь A (минимум): SRI на всё.**
- [ ] Добавить `integrity="sha384-…"` + `crossorigin="anonymous"` на Alpine.js (`base.html:29`).
      Хеш посчитать самому: `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`.
- [ ] Пройтись по ВСЕМ CDN-`<script>`/`<link>` в `src/admin/templates/**` и убедиться, что у каждого есть
      корректный `integrity` (привести список в отчёте). Версии — пиннингованы (уже так: `@x.y.z`).

**Путь B (рекомендую, чище): self-host.**
- [ ] Скачать pinned-версии (chart.js, htmx, alpine/csp, bootstrap css) в `src/admin/static/vendor/`,
      подключать с `'self'`. Удалить `https://cdn.jsdelivr.net` из `script-src` (и при возможности из
      `style-src`) в `_security_headers.py`. SRI тогда не обязателен (ресурсы свои), но версии зафиксированы
      в репозитории — supply-chain вектор закрыт полностью.
- [ ] Проверить, что админка работает: графики аналитики рисуются, htmx-подгрузки (исходы, broadcast
      preview) работают, Alpine-компоненты живые — на 1–2 экранах.

Общее:
- [ ] CSP не сломана (никаких новых `'unsafe-*'`); `ruff`/`mypy`/`pytest` зелёные.
- [ ] PR `TASK-079: CSP SRI/self-host for CDN scripts`; auto-merge по зелёному CI; `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Вне скоупа

- Менять сам набор библиотек. Только пиннинг/целостность/источник.

## Артефакты

- `* src/admin/templates/base.html` (+ analytics/list.html при self-host) — integrity/vendor-пути
- `* src/admin/_security_headers.py` — CSP (если self-host: убрать jsdelivr)
- `* (Путь B) src/admin/static/vendor/*` — локальные копии
- `* handoff/outbox/TASK-079-report.md`

## Ссылки

- `src/admin/_security_headers.py:41` — `script-src 'self' https://cdn.jsdelivr.net`
- `src/admin/templates/base.html:29` — Alpine без SRI
- Аудит: `docs/audit/2026-05-30-full-audit.md` L5; `docs/audit/2026-05-30-design-audit.md` D6
