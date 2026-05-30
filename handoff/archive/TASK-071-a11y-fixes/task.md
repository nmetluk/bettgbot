---
id: TASK-071
created: 2026-05-30
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/audit/2026-05-30-design-audit.md
  - src/admin/templates/_macros.html
  - src/admin/static/css/tokens.css
  - src/admin/templates/login.html
priority: normal
estimate: S
---

# TASK-071: a11y-фиксы админки — контраст primary-кнопки, aria-hidden на иконках, бордеры/autocomplete

## Контекст

Живой дизайн/a11y-аудит (`docs/audit/2026-05-30-design-audit.md`) нашёл системные проблемы доступности.
Блокеров нет; правки дешёвые и в общих местах. Собрано здесь одной задачей.

## Цель

Поднять доступность админки до базового WCAG AA по найденным пунктам, не меняя визуальную айдентику радикально.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-071-report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёржен.

- [ ] **D1 — контраст primary-кнопки (High).** Белый текст на бренд-цвете `#36A9E1` даёт ≈2.65:1
      (ниже AA 4.5:1). Затемнить primary-цвет до контраста ≥4.5:1 с белым (правка токена в
      `src/admin/static/css/tokens.css` / `app.css`), **либо** сделать текст primary-кнопки тёмным.
      Проверить, что это не ломает остальные использования бренд-цвета (ссылки, бейджи). Привести
      замеренный контраст в отчёте.
- [ ] **D2 — иконки не должны озвучиваться (Medium).** Material Symbols используют ligature-текст
      (`dashboard`, `folder`, `event`, `search`, `logout`, `menu`, `insights`, `shield`, …), который
      читается скринридером. Добавить `aria-hidden="true"` на иконочные элементы в **общем** месте —
      макро/партиал иконки (`src/admin/templates/_macros.html`, если иконки идут через него) — чтобы
      покрыть всю админку разом. Для кнопок/ссылок, где иконка — единственный контент, добавить
      `aria-label`. Проверить в DevTools/дереве доступности, что ligature-текст больше не экспонируется.
- [ ] **D3 — бордеры инпутов (Medium).** Бордер `#E6E6EA` на фоне `#FBFBFC` ≈1.1:1 (ниже 3:1, WCAG 1.4.11).
      Усилить цвет бордера инпутов до ≥3:1 с фоном (токен).
- [ ] **D4 — autocomplete (Low).** В `login.html`: добавить `autocomplete="username"` на поле логина и
      `autocomplete="current-password"` на пароль.
- [ ] (опц.) **D5 — график аналитики (Low).** На `/analytics` растянуть `<canvas>` графика на ширину
      карточки и задать высоту; проверить пустое состояние (0 прогнозов). Если выносится — отметить в отчёте.

### Проверка

- [ ] Контраст D1/D3 перепроверен (числами) после правки токенов.
- [ ] Дерево доступности: ligature-текст иконок не экспонируется (хотя бы на 2-3 экранах).
- [ ] `ruff`/`mypy`/`pytest` зелёные (тексты шаблонов в ассертах синхронизировать, если менялись);
      PR `TASK-071: admin a11y fixes (contrast, icon aria-hidden, input borders)`; CI зелёный; PR смёржен.
- [ ] Отчёт + archive директорией; inbox чист.

## Вне скоупа

Редизайн, изменение айдентики, новые компоненты. Только точечные a11y-правки из аудита.

## Артефакты

- `* src/admin/static/css/tokens.css` (+ `app.css`) — primary-контраст, бордеры инпутов
- `* src/admin/templates/_macros.html` (или где определены иконки) — `aria-hidden`/`aria-label`
- `* src/admin/templates/login.html` — `autocomplete`
- `* (опц.) src/admin/static/js/analytics.js` / шаблон аналитики — размер canvas
- `* handoff/outbox/TASK-071-report.md`

## Ссылки

- Источник: [`docs/audit/2026-05-30-design-audit.md`](../../docs/audit/2026-05-30-design-audit.md) (D1–D6)
- Осн. аудит (L5, CSP/SRI): [`docs/audit/2026-05-30-full-audit.md`](../../docs/audit/2026-05-30-full-audit.md)

## Подсказки исполнителю

- D1 и D2 — самые ценные и дешёвые: один токен цвета + одно место с иконками покрывают всю админку.
- Не трогай вёрстку логина сверх `autocomplete` и бордеров — она уже адаптивна и корректна.
- Иконки: если используется инлайновый `<span class="material-symbols-rounded">name</span>` без общего
  макро — заведи макро `icon(name)` с `aria-hidden="true"` и замени вхождения, иначе фиксить придётся точечно.
