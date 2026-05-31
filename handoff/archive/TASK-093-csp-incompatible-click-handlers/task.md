---
id: TASK-093
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/admin/templates/_layout_shell.html
  - src/admin/static/js/ui.js
  - docs/adr/0005-admin-v2-stack.md
  - handoff/archive/TASK-090-alpine-ui-store-init/task.md
  - handoff/inbox/TASK-088-design-conformance-to-mockup.md
priority: high
estimate: M
---

# TASK-093: `@click`-хендлеры топбара/сайдбара несовместимы с Alpine CSP — кнопки не работают

## Контекст

Живой прогон **на задеплоенном проде** (2026-05-31, cowork-аудит, после выката TASK-090)
показал: TASK-090 ([archive](../archive/TASK-090-alpine-ui-store-init/task.md)) починил
регистрацию `Alpine.store('ui')` (тема применяется из localStorage на загрузке, иконка тоггла
рендерится, акцент-свотчи появились) — **но кнопки управления UI по-прежнему не реагируют на
клик**. Проверено тремя способами (реальный клик, клик по ref, `element.click()`): тёмная тема,
плотность, акцент, гамбургер-сворачивание — все мертвы.

**Корневая причина — в консоли прода прямым текстом:**

```
Alpine Error: Alpine is unable to interpret the following expression
using the CSP-friendly build: "toggleDark()"        (button.pv-tb-iconbtn)
                                "setDensity('compact')" (button.pv-density-btn)
                                "toggleRail()"        (button.pv-tb-iconbtn)
```

CSP-friendly сборка Alpine (`alpine-csp`, принята в TASK-057) **не умеет интерпретировать вызовы
методов со скобками и аргументами** в директивах (`@click="toggleDark()"`, `setDensity('compact')`,
`setAccent('#...')`, `toggleRail()`). На странице **ноль** элементов с реально привязанным
`x-on:click` — Alpine просто не забиндил ни один обработчик. Через store API напрямую
(`Alpine.store('ui').toggleDark()`) всё работает — то есть логика стора цела, ломается именно
способ вызова из шаблона.

> Это и есть остаточная (не закрытая TASK-090) часть исходной жалобы «не переключается тёмная
> тема». TASK-090 был необходим (без стора и getters бы не работали), но недостаточен.

## Цель

Тёмная тема, плотность, акцент и сворачивание меню реально переключаются **кликом по кнопке**
(не только через store API), без Alpine-ошибок в консоли под CSP-сборкой.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-093-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Задача не закрыта, пока CI зелёный, PR смёрджен **и кликабельность подтверждена на проде в браузере**.

- [ ] Переписать event-директивы под CSP-формат. Варианты по Alpine CSP-доке
      (https://alpinejs.dev/advanced/csp):
      - без аргументов → ссылка на метод **без скобок**: `@click="toggleDark"`, `@click="toggleRail"`;
      - с аргументами (`setDensity('compact')`, `setAccent('#e6403a')`) → CSP не поддерживает
        inline-аргументы: завести no-arg методы (`densityCompact`/`densityRegular`/`densityComfortable`)
        **или** один метод, читающий значение из `data-*` текущего элемента через `this.$el.dataset`
        (event-обработчику доступен `$el`). Выбрать единый подход и описать в отчёте.
- [ ] Привести в соответствие `uiState`-компонент в `ui.js` (методы под новый способ вызова).
- [ ] Проверка **в браузере** (обязательно, юнит не ловит): клик по тогглу меняет тему и
      `data-theme`, переживает перезагрузку (localStorage); C/R/K меняют `data-density`; свотчи
      меняют акцент; гамбургер сворачивает сайдбар. DevTools-консоль **без** `Alpine Error … CSP`.
- [ ] Регрессия: тест/ассерт, что в шаблонах нет `@click` с `()`/аргументами (grep-guard в тестах
      или линт-правило), чтобы CSP-несовместимый синтаксис не вернулся незаметно.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные.
- [ ] PR открыт `TASK-093: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] **После выката на прод** — прокликать тему/плотность/акцент/меню в браузере. Зафиксировать в отчёте.
- [ ] Отчёт `handoff/outbox/TASK-093-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`) — оставить директорию
      `handoff/archive/TASK-093-<slug>/task.md`, без залипших `.in-progress`.

## Артефакты

- `* src/admin/templates/_layout_shell.html` — `@click` тоггла/плотности/акцента/гамбургера
- `* src/admin/static/js/ui.js` — методы `uiState` под CSP-формат вызова
- любые другие шаблоны с `@click="...(...)"` (проверить grep по `@click=".*("`)
- `* tests/...` — grep-guard на CSP-несовместимый синтаксис

## Подсказки исполнителю

- НЕ возвращать `unsafe-eval`/обычную сборку Alpine — CSP-сборка принята осознанно (TASK-057).
  Чинить синтаксис директив, а не сборку.
- Проверять обязательно в реальном браузере: тут юнит-тест бесполезен (он зелёный, а кнопки мертвы).
- `parallel-safe: false` — трогает `_layout_shell.html` (топбар), пересекается с **TASK-088**
  (там M3 причёсывает топбар) — брать **до** TASK-088. То есть последовательность фронта:
  TASK-093 → TASK-088. (TASK-088 уже `blockedBy: [TASK-090, TASK-091]`; владельцу/архитектору
  стоит добавить туда и TASK-093, либо просто держать порядок вручную.)
- Grep для инвентаризации: `@click=` по `src/admin/templates/**`.
