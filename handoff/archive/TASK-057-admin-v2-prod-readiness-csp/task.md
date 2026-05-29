---
id: TASK-057
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/_security_headers.py
  - src/admin/templates/base.html
  - docs/adr/0005-admin-v2-stack.md
priority: high
estimate: S
---

# TASK-057: Прод-готовность админки v2 — починить CSP (шрифты + Alpine)

## Контекст

Миграция админки на v2 завершена (TASK-053…056). Перед закреплением на проде нужно убедиться,
что v2 вообще работает под продовыми security-заголовками. **Сейчас не работает:** CSP из TASK-037
(`src/admin/_security_headers.py`) не пропускает то, что добавил v2-`base.html`:

1. **Material Symbols (иконки).** `base.html` грузит CSS с `https://fonts.googleapis.com`, а сами
   шрифты — с `https://fonts.gstatic.com`. В текущем CSP `style-src` не содержит googleapis, а
   `font-src` вообще не задан (→ падает на `default-src 'self'`). Итог на проде: **иконки не
   загрузятся**, вёрстка поедет.
2. **Alpine.js.** Стандартная сборка Alpine вычисляет выражения через `new Function()`, что требует
   `script-src 'unsafe-eval'`. В текущем CSP его нет → **тогглы темы/плотности/акцента молча не
   заработают** в проде (в dev без CSP — работают, поэтому при ручной проверке локально баг не виден).

Это классический «работает в dev, ломается за CSP на проде». Прод сейчас — no-domain + ssh-tunnel
(см. `docs/07-deployment.md`, `docs/runbook-dr.md`); сам redeploy делает владелец (executor на прод
не выкатывает — см. CLAUDE.md). Задача — сделать v2 **прод-готовым** и проверяемым.

## Цель

Админка v2 полностью функциональна под продовым CSP: иконки грузятся, Alpine-тогглы работают, при
этом CSP не ослаблен сверх необходимого.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-057-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).

- [ ] CSP в `_security_headers.py` пропускает шрифты: `style-src` += `https://fonts.googleapis.com`; добавлен `font-src 'self' https://fonts.gstatic.com`.
- [ ] Решён вопрос с Alpine под CSP **одним из двух способов** (выбор обосновать в отчёте):
  - (A) перейти на CSP-сборку `@alpinejs/csp` и убрать инлайн-выражения из `base.html`
    (`x-data="{ dark: $store.ui.dark }"`, `:data-theme="..."` на `<html>`) — перенести логику в
    зарегистрированные `Alpine.data()` / `Alpine.store()`; **CSP не ослабляется** (рекомендуется);
  - (B) добавить `'unsafe-eval'` в `script-src` — проще, но ослабляет CSP; допустимо только с явным
    обоснованием, что админка внутренняя (no-domain + ssh-tunnel).
- [ ] Проверено end-to-end, что Alpine реально работает: тогглы тёмной темы / плотности / акцента
  переключают UI и переживают перезагрузку (localStorage). Заодно проверить рассинхрон `<html>`
  `x-data="{ dark: $store.ui.dark }"` ↔ `body x-data="uiState"` (сейчас `$store.ui` может быть не
  определён — убедиться, что тема на `<html>` применяется).
- [ ] Тест на CSP: в `tests/unit/admin/` есть проверка, что заголовок CSP содержит
  `fonts.googleapis.com`, `font-src`/`fonts.gstatic.com` и (если выбран путь B) `unsafe-eval`.
- [ ] `make prod.smoke` / `scripts/smoke_test.sh` при необходимости дополнен проверкой, что
  `/login` отдаёт 200 и подключает шрифты/Alpine (по возможности; не блокер, если smoke не про CSP).
- [ ] `uv run pytest` зелёный полностью; `ruff`/`mypy` чисто; PR `TASK-057: ...`; CI зелёный; смёрджено.
- [ ] Отчёт + archive директорией (см. `handoff/README.md`).

## Артефакты

- `* src/admin/_security_headers.py` — CSP (fonts + возможно unsafe-eval)
- `* src/admin/templates/base.html` — при пути A: рефактор инлайн-выражений
- `* src/admin/static/js/ui.js` — при пути A: регистрация store/data под CSP-сборку
- `+ tests/unit/admin/test_security_headers.py` (или дополнение существующего) — проверка CSP

## Ссылки

- CSP: [`src/admin/_security_headers.py`](../../src/admin/_security_headers.py) (TASK-037)
- Деплой: [`docs/07-deployment.md`](../../docs/07-deployment.md), [`docs/runbook-dr.md`](../../docs/runbook-dr.md)
- Решение по стеку v2: [`docs/adr/0005-admin-v2-stack.md`](../../docs/adr/0005-admin-v2-stack.md)

## Подсказки исполнителю

- Alpine CSP-сборка: `https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.x/dist/cdn.min.js`. В ней
  разрешены только зарегистрированные имена — инлайн JS-выражения в атрибутах не исполняются.
  `ui.js` уже использует `Alpine.data('uiState', …)` — это правильный паттерн; останется убрать
  инлайн-выражения из `base.html` и при необходимости завести `Alpine.store('ui', …)`.
- После правки CSP проверь в браузере devtools Console на проде/стейдже отсутствие
  `Refused to load …`/`unsafe-eval` ошибок.
