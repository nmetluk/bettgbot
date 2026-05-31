---
id: TASK-092
created: 2026-05-31
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/routes/broadcasts.py
  - src/admin/routes/audit.py
  - src/admin/templates/broadcasts/form.html
  - src/admin/templates/audit/_details.html
  - handoff/archive/TASK-089-broadcasts-new-500/task.md
  - handoff/archive/TASK-091-audit-details-and-search/task.md
priority: high
estimate: M
---

# TASK-092: На проде всё ещё 500 — `/broadcasts/new` и `/audit/{id}/details`

## Контекст

Живой прогон **на задеплоенном проде** `a.pinbetting.ru` (2026-05-31, cowork-аудит, после
выката TASK-089/090/091) показал, что два эндпоинта по-прежнему падают с HTTP 500 — несмотря
на то что соответствующие фиксы влиты в `main` и задеплоены:

1. **`GET /broadcasts/new` → 500.** TASK-089 ([archive](../archive/TASK-089-broadcasts-new-500/task.md))
   убрал `csrf_token` из контекста и сделал шаблон защитным, добавил unit-тест
   `test_new_broadcast_form_renders_200` (зелёный в CI). Но на проде форма всё равно отдаёт
   `Internal Server Error` (статус-код 500 подтверждён в Network). → причина 500 либо не только
   в `csrf_token`, либо тест с моками не воспроизводит боевые условия.

2. **`GET /audit/{id}/details` → 500.** TASK-091 ([archive](../archive/TASK-091-audit-details-and-search/task.md))
   починил привязку (`#audit-row-{{id}}` теперь существует под `hx-target`), и HTMX-запрос
   действительно уходит на правильный URL — но сервер на нём отвечает 500, поэтому детали записи
   аудита по-прежнему не раскрываются. Проверено: клик по шеврону → `GET /audit/16/details` → 500.

**Общий признак:** оба — серверные 500 на GET-эндпоинтах админки, при этом unit-тесты с
моками/TestClient зелёные. Высока вероятность **общей причины**, которую тесты не ловят
(например, обращение к `request.state.*`/контексту, отсутствующему в реальном GET-потоке;
расхождение схемы/миграций на проде; падающий запрос к БД на реальных данных; зависимость,
не инициализированная в боевом конфиге). Стоит сначала снять боевые traceback'и обоих и
проверить, не одна ли это первопричина.

## Цель

`GET /broadcasts/new` и `GET /audit/{id}/details` отдают 200 на проде; форма рассылки
открывается, детали аудита раскрываются по клику. Тесты воспроизводят боевые условия, а не
только happy-path с моками.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-092-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Задача не закрыта, пока CI зелёный, PR смёрджен **и фикс подтверждён на проде** (200, не 500).

- [ ] Снять реальные traceback'и обоих 500 с прода (логи контейнера web / `docker logs`),
      приложить в отчёт. Не гадать по коду — получить стек.
- [ ] Определить, общая ли первопричина у двух эндпоинтов; устранить.
- [ ] `GET /broadcasts/new` → 200, форма + HTMX-превью получателей работают.
- [ ] `GET /audit/{id}/details` → 200, детали записи раскрываются (HTMX-swap в `#audit-row-{id}`).
- [ ] Тесты, **воспроизводящие боевой путь** (не только моки): пройти реальный GET через
      middleware-стек так, как это происходит на проде (csrf/CSP/контекст). Тест должен ловить
      именно тот 500, что наблюдался. Существующий `test_new_broadcast_form_renders_200` усилить
      или заменить, т.к. он давал ложноположительный результат.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные.
- [ ] PR открыт `TASK-092: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] **После выката на прод** — прокликать оба сценария в браузере: 200, не 500. Зафиксировать в отчёте.
- [ ] Отчёт `handoff/outbox/TASK-092-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`): перед `archive`-коммитом
      `ls handoff/inbox/ | grep TASK-092` — убрать обе копии, оставить **директорию**
      `handoff/archive/TASK-092-<slug>/task.md`. (Прецеденты дрейфа: 089/090/091 закрывались с
      залипшим `.in-progress` — не повторять.)

## Артефакты

- `* src/admin/routes/broadcasts.py` — handler `GET /broadcasts/new`
- `* src/admin/routes/audit.py` — handler `GET /audit/{id}/details`
- `* src/admin/templates/broadcasts/form.html`, `audit/_details.html` — при необходимости
- `* tests/...` — тесты, воспроизводящие боевой путь (не только моки)

## Подсказки исполнителю

- Это **серверные** 500 — смотреть traceback приложения (логи web-контейнера), а не консоль браузера.
- Unit-тест на `/broadcasts/new` уже был и дал ложноположительный результат → не доверять
  «зелёному CI» как признаку готовности (см. handoff-практику проверки против прода).
- Проверь гипотезу общей причины: оба — GET, оба, возможно, читают что-то из `request.state`
  или общий контекст-процессор/шаблонный глобал, который на реальном GET-потоке не выставлен.
- `parallel-safe: true` — backend-эндпоинты, не пересекается с фронтовой TASK-093 и CSS-TASK-088.
