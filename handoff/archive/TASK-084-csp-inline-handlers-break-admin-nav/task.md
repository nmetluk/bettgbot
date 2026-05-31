---
id: TASK-084
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/_security_headers.py
  - src/admin/templates/events/list.html
  - src/admin/templates/events/form.html
  - src/admin/templates/base.html
priority: high
estimate: M
---

# TASK-084: CSP `script-src 'self'` блокирует инлайновые on*-обработчики → навигация админки не работает

## Симптомы (из теста владельца, блокирует релиз v0.1.0)

- «Невозможно перейти к редактированию события» — клик по строке в списке событий не навигирует.
- «Невозможно внести итоги/прогнозы» — на форме события не переключаются вкладки «Исходы»/«Результат».

## Корневая причина

`src/admin/_security_headers.py`: CSP `script-src 'self'` (БЕЗ `'unsafe-inline'`). Браузер при этом
блокирует все инлайновые обработчики событий (`onclick=` и т.п.) — в консоли
`Refused to execute inline event handler because it violates the following CSP directive`.

Навигация админки построена на инлайновых `on*=`:
- `events/list.html:62` — `<tr onclick="window.location='/events/{id}'">` (переход к редактированию).
- `events/form.html:89/94/99` — табы Данные/Исходы/Результат через `onclick="window.location=…?tab=…"`.
- `events/form.html:167` — `onclick="return confirm(...)"` на «Зафиксировать».
- Аналогично инлайновые `on*=` в: `categories/form.html`, `users/list.html`, `users/detail.html` (×2),
  `analytics/list.html`, `leaderboard/list.html`, `dashboard.html`.

`style-src` содержит `'unsafe-inline'`, поэтому инлайновые `style=` работают — а `script-src` нет
(и **добавлять `'unsafe-inline'` в script-src НЕЛЬЗЯ** — это вернёт XSS-вектор; чиним правильно).

## Цель

Убрать все инлайновые `on*=` из шаблонов админки, заменив на CSP-совместимые паттерны
(внешний JS из `'self'` + `data-`атрибуты, либо обычные `<a href>`), не ослабляя CSP.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-084-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

- [ ] **Внешний JS** (напр. `src/admin/static/js/ui.js`), подключён в `base.html` через
      `<script src="/static/js/ui.js" defer>` (это `'self'` — CSP пропускает). Реализовать через
      делегирование событий:
      - кликабельные строки: `<tr data-href="/events/{id}">` → listener делает `window.location`;
      - подтверждения: `data-confirm="текст"` на кнопке/форме → listener вызывает `confirm()` и
        отменяет сабмит при отказе.
- [ ] **Табы формы события** — заменить `<button onclick=window.location>` на обычные `<a href="/events/{id}?tab=…">`
      со стилем таба (проще всего и без JS). Disabled-таб (результат недоступен) — оставить визуально
      неактивным без ссылки.
- [ ] **Пройтись по ВСЕМ шаблонам** и убрать инлайновые `on*=` (события, категории, пользователи,
      аналитика, лидерборд, дашборд). Список — `grep -rnE 'on(click|change|submit|input|load)=' src/admin/templates/`.
      Ни одного инлайнового обработчика не должно остаться.
- [ ] **CSP не трогать** (никакого `'unsafe-inline'`/`'unsafe-hashes'` в `script-src`).
- [ ] **Регресс-гард в CI:** добавить проверку (в существующий тест или маленький скрипт/pytest),
      которая падает, если в `src/admin/templates/**` появляется инлайновый `on*=`-обработчик.
      Это не даст повторить регрессию.
- [ ] **Фактическая проверка флоу** (в отчёт): с активной CSP — клик по строке открывает событие,
      табы Данные/Исходы/Результат переключаются, добавление исходов и фиксация результата работают,
      в консоли нет CSP-violation'ов. Желательно через Chrome/headless; либо описать ручную проверку
      на запущенной админке.
- [ ] `ruff`/`mypy`/`pytest` зелёные (тексты шаблонов в ассертах синхронизировать, если менялись);
      PR `TASK-084: replace inline event handlers (CSP-safe nav)`; auto-merge; `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Важно для релиза

Это блокирует v0.1.0. Тег `v0.1.0` сейчас на `c0bfe43` — **после фикса релизный тег нужно
пересоздать на новом коммите** (с фиксом). Перетегирование сделает архитектор/владелец, НЕ исполнитель.

## Вне скоупа

- Редизайн UI, новые экраны. Только перевод обработчиков на CSP-safe без изменения поведения/вида.
- Ослабление CSP — запрещено.

## Артефакты

- `* src/admin/static/js/ui.js` — делегирование (data-href, data-confirm)
- `* src/admin/templates/base.html` — подключение ui.js
- `* src/admin/templates/**` — убрать инлайновые on*=, проставить data-атрибуты / <a>
- `* tests/...` — гард против инлайновых on*=
- `* handoff/outbox/TASK-084-report.md`

## Ссылки

- `src/admin/_security_headers.py` — CSP `script-src 'self'`
- Инлайновые обработчики: `grep -rnE 'on(click|change|submit|input|load)=' src/admin/templates/`
- Прецедент CSP-совместимости: TASK-060 (графики аналитики через внешний JS)
