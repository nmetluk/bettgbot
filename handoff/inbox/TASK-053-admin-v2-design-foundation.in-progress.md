---
id: TASK-053
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/adr/0005-admin-v2-stack.md
  - docs/05-admin-spec.md
  - sessions/2026-05-29-01-admin-design/artifacts/admin/
priority: high
estimate: M
---

# TASK-053: Фундамент дизайн-системы админки v2 (токены + layout-shell + Alpine.js)

## Контекст

Дизайнеры передали прототип админки v2 (React, заморожен как визуальный эталон) —
`sessions/2026-05-29-01-admin-design/artifacts/admin/`. Принят [ADR 0005](../../docs/adr/0005-admin-v2-stack.md),
**вариант C**: продакшен остаётся на SSR (FastAPI + Jinja2 + HTMX + Alpine.js), а из прототипа
берётся визуальный язык — дизайн-токены `--pv-*`, светлая/тёмная тема, плотность таблиц,
настраиваемый акцент, общий layout (sidebar + topbar).

Это **фундаментная** задача: она готовит базу, на которую затем поэкранно переносятся
TASK-054…TASK-056. Существующие шаблоны админки (TASK-019…026) переводятся на новый base-шаблон
в последующих задачах, не здесь.

## Цель

Перенести дизайн-систему прототипа в собственный CSS проекта и собрать базовый layout-shell
(каркас страницы с навигацией и топбаром), управляемый темой/плотностью/акцентом через Alpine.js,
без какого-либо SPA.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — написать `handoff/outbox/TASK-053-report.md`.

- [ ] Токены из `artifacts/admin/styles.css` (`--pv-*`: цвета, радиусы, тени, типографика) перенесены в `src/admin/static/css/tokens.css` (или эквивалент), включая значения для светлой и тёмной темы (`[data-theme="dark"]`) и плотности (`[data-density]`).
- [ ] Создан/обновлён базовый шаблон `src/admin/templates/base.html`: sidebar (разделы «Управление» / «Журнал» / «Развитие» как в `shell.jsx`), topbar, контейнер контента; разметка использует токены, а не хардкод цветов.
- [ ] Подключён Alpine.js (3.x) — локально или из CDN согласно конвенциям деплоя; реализованы клиентские тогглы: тёмная тема, плотность таблиц, акцент. Выбор сохраняется (localStorage) и переживает перезагрузку.
- [ ] Bootstrap 5 остаётся базой компонентов; собственный CSS лежит поверх (override), а не вместо.
- [ ] Никакого React/SPA, никакого build-pipeline сверх существующего: только статические CSS/JS-ассеты.
- [ ] Демонстрационная страница или существующий `/login` отрисованы на новом base — видно тему/плотность/акцент в действии.
- [ ] `ruff`/`mypy` (если затронут Python) зелёные; PR открыт `TASK-053: ...`; CI зелёный.
- [ ] Отчёт `handoff/outbox/TASK-053-report.md` написан.
- [ ] 🚨 Move-семантика inbox→archive: перед `chore(handoff): archive TASK-053` проверить `ls handoff/inbox/ | grep TASK-053`, `git rm` лишние копии.

## Артефакты

- `+ src/admin/static/css/tokens.css` — токены v2 (light/dark/density)
- `* src/admin/templates/base.html` — layout-shell
- `+ src/admin/static/js/ui.js` (или Alpine inline) — тогглы темы/плотности/акцента
- `* src/admin/static/` — подключение Alpine.js
- `* docs/05-admin-spec.md` — НЕ трогать (зона проектировщика); расхождения — вопросом в outbox

## Ссылки

- Решение: [`docs/adr/0005-admin-v2-stack.md`](../../docs/adr/0005-admin-v2-stack.md)
- Спецификация: [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md)
- Визуальный эталон: `sessions/2026-05-29-01-admin-design/artifacts/admin/` (`styles.css`, `shell.jsx`, `index.html`, `screens/`)

## Подсказки исполнителю

- Прототип использует `color-mix()` для производных акцента (см. `app.jsx`) — в CSS это поддерживается современными браузерами; можно повторить или предрассчитать палитру.
- `app.jsx` выставляет `data-theme` / `data-density` на `documentElement` — та же модель удобна и для Alpine.
- Иконки в прототипе — Material Symbols (имена в `shell.jsx`); согласовать способ подключения (шрифт-иконки или SVG) и при необходимости задать вопрос в outbox.
