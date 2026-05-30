---
id: TASK-070
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/templates/_layout_shell.html
  - src/admin/templates/base.html
  - src/admin/templates/dashboard.html
priority: high
estimate: M
---

# TASK-070: BLOCKER — контент всех страниц админки рендерится НИЖЕ шелла (пустой <main>)

## Контекст (диагностировано вживую в браузере на проде, после полного деплоя)

Залогинившись (через обходняк со свежей кукой), вижу: на КАЖДОЙ авторизованной странице сайдбар и топбар
на месте, но **основная область пустая**, а реальный контент (заголовок, фильтры, таблицы) отрисован
**ниже всего шелла**, под вьюпортом. Это и есть «основной блок отображается ниже меню, а не рядом».

Замеры в DOM (`/events`): grid-контейнер `.pv-app` (`display:grid`, `grid-template-rows: 56px 665px`)
имеет ровно 3 дочерних — `aside.pv-sidebar`, `header.pv-topbar`, `main.pv-main`, причём **`<main>` пустой**.
Контент (`h1.pv-page-title`, форма, `table.pv-table`) лежит в отдельном контейнере **вне** `<main>` и вне
сетки (`top≈745px`, ниже грида высотой 721px) → визуально пусто.

**Первопричина — Jinja-блок внутри `{% include %}`.** Все авторизованные страницы устроены так
(пример `events/list.html`, идентично в остальных):

```jinja
{% extends "base.html" %}
{% block body %}
{% include "_layout_shell.html" %}      {# шелл подключается как include #}

{% block pv_content %}                  {# а это — отдельный блок прямо в body #}
   …контент страницы…
{% endblock %}
{% endblock %}
```

`_layout_shell.html` — обычный partial (без `extends`), внутри `<main class="pv-main">{% block pv_content %}{% endblock %}</main>`.
**Jinja НЕ прокидывает переопределение блока в подключаемый через `{% include %}` шаблон.** Поэтому:
- подключённый шелл рендерит свой `{% block pv_content %}` **пустым** → `<main>` пустой;
- `{% block pv_content %}…{% endblock %}`, объявленный в `body` страницы, рендерится инлайн **в body, после
  шелла** → контент уезжает вниз, под сетку.

Симптом одинаков на всех 12 авторизованных шаблонах (см. список). Скорее всего, это было сломано
изначально, а заметили только сейчас — раньше в админку нельзя было войти (CSRF-блокеры 062/063/068/069).

## Цель

Контент каждой авторизованной страницы рендерится **внутри** `<main class="pv-main">`, в правой нижней
ячейке грида рядом с сайдбаром — на всех страницах админки. Шелл (сайдбар/топбар/скрипты) не дублируется.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-070-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёржен.

Перейти с анти-паттерна «include + block в body» на нормальное **наследование шаблонов**:

- [ ] **`_layout_shell.html`** делает `{% extends "base.html" %}` и оборачивает грид в `{% block body %}`:
      весь `<div class="pv-app">…</div>` (сайдбар + топбар + `<main class="pv-main">{% block pv_content %}{% endblock %}</main>`)
      внутри `{% block body %}`. Скрипт `ui.js`, который сейчас в конце шелла, перенести в
      `{% block scripts_extra %}` (или оставить в body шелла так, чтобы он грузился один раз).
- [ ] **Каждая авторизованная страница** (12 шт., см. список) меняет `{% extends "base.html" %}` →
      `{% extends "_layout_shell.html" %}`, **убирает** обёртку `{% block body %}` и строку
      `{% include "_layout_shell.html" %}`, оставляя `{% block pv_content %}…{% endblock %}` как
      прямой блок. `{% block title %}`, `{% block head_extra %}`, `{% block scripts_extra %}` продолжают
      работать по цепочке наследования (страница → `_layout_shell.html` → `base.html`).
- [ ] Проверить страницы с доп-ассетами: `events/form.html` (`head_extra`), `analytics/list.html`
      (внешний JS под CSP, TASK-060), `broadcasts/form.html` (`broadcasts.js`, TASK-061-amendment) —
      их `{% block scripts_extra %}`/`head_extra` должны по-прежнему подключаться.
- [ ] `git grep -n 'include "_layout_shell.html"' src/admin/templates/` → **пусто** после рефактора.
- [ ] `git grep -n 'extends "base.html"' src/admin/templates/` → остаётся только у `login.html` и
      `_layout_shell.html` (логин использует собственную центрированную вёрстку, его НЕ трогаем).

### Список затронутых шаблонов

```
analytics/list.html   audit/list.html        broadcasts/form.html   broadcasts/list.html
categories/form.html  categories/list.html   dashboard.html         events/form.html
events/list.html      leaderboard/list.html  users/detail.html      users/list.html
```

### Проверка

- [ ] Существующие unit-тесты хендлеров рендерят эти шаблоны (TemplateResponse) — должны остаться зелёными;
      ошибка наследования сломала бы рендер и упала бы в тестах. По возможности добавить простую проверку,
      что в ответе `<main class="pv-main">` НЕ пустой (содержит маркер контента, напр. `pv-page-title`) —
      это поймало бы регресс именно этого бага.
- [ ] `ruff`/`mypy`/`pytest` зелёные; PR `TASK-070: fix admin layout — content inside <main> via template inheritance`;
      CI зелёный; PR смёржен; handoff закрыт (отчёт + archive директорией; inbox чист).
- [ ] Локальная визуальная проверка хотя бы 2-3 страниц (например, `/`, `/events`, `/users`): контент
      рядом с сайдбаром, не ниже. Отразить в отчёте.

## После мёржа

- [ ] Владелец передеплоит web (`docker compose pull web && up -d --force-recreate web`).
- [ ] Cowork перепроверит в браузере: на `/`, `/events`, `/users`, `/analytics` контент в `<main>`, лейаут корректен.

## Вне скоупа

- CSRF-фикс старой куки — отдельная задача TASK-069 (в работе).
- a11y-находки страницы логина (контраст кнопки, ligature-иконки, бордеры инпутов) — отдельно, не здесь.

## Артефакты

- `* src/admin/templates/_layout_shell.html` — `extends base` + `block body`
- `* ` все 12 авторизованных шаблонов — `extends _layout_shell`, убрать include/обёртку body
- `* tests/...` — (опц.) проверка непустого `<main>`
- `* handoff/outbox/TASK-070-report.md`

## Ссылки

- Живой замер: `.pv-app` 3 ребёнка, `<main>` пустой, контент на `top≈745` (ниже грида).
- Анти-паттерн: `events/list.html` строки 1-8 (`extends base` → `block body` → `include shell` → `block pv_content`).
- Шелл: `src/admin/templates/_layout_shell.html` (`<main>{% block pv_content %}{% endblock %}</main>`, строки 129-131).

## Подсказки исполнителю

- Корень — `{% block %}` внутри `{% include %}` в Jinja не переопределяется родителем. Лечится переходом
  на `extends` (наследование), а не `include`.
- Делай аккуратно по одному шаблону, прогоняя рендер-тест соответствующего хендлера. Логин (`login.html`)
  НЕ трогать — у него своя вёрстка без шелла.
- После рефактора убедись, что `ui.js`, `analytics.js`, `broadcasts.js` и `head_extra`-стили грузятся
  ровно один раз и под CSP (без инлайна).
