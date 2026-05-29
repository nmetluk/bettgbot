---
id: TASK-060
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/archive/TASK-059-admin-analytics/task.md
  - src/admin/_security_headers.py
  - src/admin/templates/analytics/list.html
priority: high
estimate: S
---

# TASK-060: Графики аналитики через внешний JS — инлайн-скрипт блокируется CSP

## Контекст

TASK-059 смёржил экран `/analytics`, но его шаблон инициализирует Chart.js
**инлайн-скриптом** (`src/admin/templates/analytics/list.html`, блок `<script> … new Chart(…) </script>`,
данные через `{{ … | tojson }}`).

CSP админки (TASK-057, `src/admin/_security_headers.py`) задаёт:

```
script-src 'self' https://cdn.jsdelivr.net;
```

— **без** `'unsafe-inline'` и **без** nonce-механизма (его в проекте нет). Значит инлайн-`<script>`
с исполняемым кодом браузер **блокирует**. Результат на проде: библиотека Chart.js по `src=`
с jsdelivr грузится, но **код инициализации не выполняется** → линейный график «динамика по дням»
и столбчатый «точность по категориям» **не отрисовываются**; таблицы (воронка, топ-события) работают,
т.к. это обычный HTML.

Это регрессия CSP-инварианта из TASK-057: шаблон аналитики — **единственный** в админке с инлайн-`<script>`
(`git grep '<script>' src/admin/templates/` → только `analytics/list.html`). TASK-057 специально убрал
инлайн-скрипты и перевёл Alpine на CSP-сборку именно ради `script-src` без `unsafe-inline`.

Почему CI зелёный, а фича сломана: юнит-тест `test_analytics_renders_chart_script` проверяет лишь
**наличие строки** `new Chart`/данных в HTML, а не реальное исполнение под CSP в браузере. Задача
TASK-059 прямо предупреждала «проверь devtools-консоль на CSP-ошибки; не ослабляй CSP молча» —
проверка в браузере не была сделана.

Data/service/route-слой TASK-059 проверен и корректен (гарды деления на ноль: `having(resolved > 0)`,
`cast(...NUMERIC)`, воронка `if total else 0.0`) — **трогать не нужно**. Чинить только доставку JS на экран.

## Цель

Оба графика аналитики отрисовываются под **существующим** строгим CSP, **без ослабления CSP**
(никаких `unsafe-inline`/`unsafe-eval`/nonce).

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-060-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).

**Реализация:**

- [ ] Вынести инициализацию Chart.js из инлайн-`<script>` в внешний файл `src/admin/static/js/analytics.js`
      (отдаётся с `'self'` — разрешено `script-src`). Подключение: `<script src="/static/js/analytics.js" defer></script>`
      **после** тега загрузки Chart.js с jsdelivr.
- [ ] Данные для графиков передавать **неисполняемым** блоком данных, который CSP `script-src` не контролирует:
      `<script type="application/json" id="analytics-data">{{ {...} | tojson }}</script>`
      (тип `application/json` — это данные, а не скрипт, поэтому CSP не блокирует). `analytics.js` на
      `DOMContentLoaded` читает `JSON.parse(document.getElementById('analytics-data').textContent)` и строит графики.
      Допустима альтернатива через `data-*`-атрибуты canvas — на выбор, отразить в отчёте.
- [ ] В шаблонах админки **не остаётся ни одного инлайн исполняемого** `<script>`:
      `git grep -n '<script>' src/admin/templates/` → пусто. CSP-заголовок (`_security_headers.py`) **не меняется**.
- [ ] Библиотека Chart.js по-прежнему грузится тегом `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/...">`
      (разрешено `script-src`).
- [ ] Пустые состояния по-прежнему не падают (нет данных → нет canvas-инициализации либо пустой ряд без ошибок в консоли).

**Качество:**

- [ ] Обновить юнит-тест `tests/unit/admin/test_analytics_handler.py`
      (`test_analytics_renders_chart_script` и при необходимости соседние): ассертить наличие
      `<script src="/static/js/analytics.js"` **и** блока `type="application/json" id="analytics-data"`
      с ожидаемыми ключами, **вместо** проверки инлайнового `new Chart`. Текст шаблона меняешь —
      синхронно правь текстовые ассерты тестов.
- [ ] **Браузерная проверка (обязательна, описать в отчёте):** открыть `/analytics`, devtools-консоль —
      **ноль CSP-violation'ов**; оба графика рисуются; таблицы воронки и топ-событий не затронуты.
      Прогнать на состоянии «есть данные» и «данных нет».
- [ ] `uv run pytest` зелёный полностью; `ruff check`/`ruff format`/`mypy` чисто; PR `TASK-060: ...`;
      CI зелёный; PR смёрджен; локальная `main` синхронизирована.
- [ ] Отчёт `handoff/outbox/TASK-060-report.md` + archive **директорией**
      (`handoff/archive/TASK-060-analytics-csp-charts/task.md`).
- [ ] **🚨 Move-семантика inbox→archive:** перед `chore(handoff): archive` —
      `ls handoff/inbox/ | grep TASK-060`; если что-то нашлось — `git rm` все копии
      (`TASK-060-*.md` и `TASK-060.in-progress.md`). В archive — **одна** копия.

## Вне скоупа

- Любые изменения CSP-заголовка. Если внезапно окажется, что Chart.js требует чего-то сверх
  `script-src 'self' https://cdn.jsdelivr.net` (не должно — внешний JS + json-блок достаточны) —
  это **открытый вопрос**: оформи `handoff/outbox/TASK-060-question.md`, **не** ослабляй CSP молча.
- Новые метрики, редизайн графиков, экспорт, диапазон дат — это будущие задачи.
- Data/service/route-слой TASK-059 — корректен, не рефакторить.

## Артефакты

- `+ src/admin/static/js/analytics.js` — новый, вся инициализация графиков
- `* src/admin/templates/analytics/list.html` — убрать инлайн-init, добавить внешний `<script src>` + json-блок данных
- `* tests/unit/admin/test_analytics_handler.py` — обновить ассерты
- (роут `src/admin/routes/analytics.py` менять не требуется — данные уже передаются в шаблон)

## Ссылки

- CSP: [`src/admin/_security_headers.py`](../../src/admin/_security_headers.py) (`script-src 'self' https://cdn.jsdelivr.net`)
- Прецедент CSP-сборки без инлайна: TASK-057 (`ui.js` + `Alpine.store`), `handoff/archive/TASK-057-admin-v2-prod-readiness-csp/`
- Статика монтируется в `src/admin/app.py` (`StaticFiles`, `/static`) — добавлено в TASK-019
- Шаблон с дефектом: `src/admin/templates/analytics/list.html` (строки ~126–205)

## Подсказки исполнителю

- `<script type="application/json">` **не** подпадает под `script-src` — это валидный паттерн «данные в HTML
  под строгим CSP» (аналог Django `json_script`). Это и есть штатный способ, не nonce.
- Порядок загрузки: тег Chart.js (jsdelivr) → затем `analytics.js` с `defer`; внутри — слушать `DOMContentLoaded`
  или полагаться на `defer`-порядок. Проверь, что `Chart` определён к моменту вызова.
- Не добавляй nonce-инфраструктуру — для статического JS + json-блока она не нужна и усложнит CSP.
- Проверка глазами в браузере — ключевой DoD-пункт: юнит-тест на строки CSP-block не ловит (как и в TASK-057).
