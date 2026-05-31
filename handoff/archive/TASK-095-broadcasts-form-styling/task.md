---
id: TASK-095
created: 2026-06-01
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/templates/broadcasts/form.html
  - src/admin/templates/categories/form.html
  - src/admin/static/css/app.css
  - handoff/archive/TASK-088-design-conformance-to-mockup/task.md
priority: normal
estimate: S
---

# TASK-095: Привести форму рассылки `/broadcasts/new` к дизайн-системе

## Контекст

Финальная приёмка 088 на проде (2026-06-01, cowork, живой прогон): все страницы из скоупа 088
оформлены корректно — **кроме формы создания рассылки** `/broadcasts/new`. Форма открывается
(500 починен в TASK-092), но **свёрстана криво**: лейблы плывут, textarea перекрывает текст,
сегменты/счётчик/предпросмотр идут «голым HTML».

**Причина — тот же класс бага, что блок C в 088** (классы без стилей), просто форма
(`broadcasts/form.html`) не была в списке артефактов 088 (там был только `broadcasts/list.html`).
Шаблон использует целое семейство классов, которых **нет в `app.css`**:

```
pv-form-group, pv-form-label, pv-form-control, pv-form-help, pv-form-actions,
pv-segment-choices, pv-segment-choice, pv-segment-label, pv-segment-title, pv-segment-desc,
pv-broadcast-preview, pv-bubble
```

При этом рабочие формы (`categories/form.html`, события) построены на **других, определённых**
классах: `pv-stack`, `pv-field-label`, `pv-input`, `pv-textarea`, `pv-field-help`, `pv-card-body`,
`pv-grid`, `pv-btn*`. (Шапка страницы `pv-page*` у формы рассылки уже корректна — она определена.)

## Цель

`/broadcasts/new` выглядит как остальные формы админки: поля, лейблы, выбор сегмента, поле
текста с счётчиком, предпросмотр и кнопки оформлены по дизайн-системе, без «голого HTML».

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-095-report.md`.** Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Не закрыто, пока CI зелёный, PR смёрджен **и оформление подтверждено на проде в браузере**.

- [ ] Перевести `broadcasts/form.html` на **существующие** классы дизайн-системы (как в
      `categories/form.html`): обычные поля — `pv-stack` + `pv-field-label` + `pv-input`/`pv-textarea`
      + `pv-field-help`; контейнер — `pv-card`/`pv-card-body`; кнопки — `pv-btn*`. Заменить
      `pv-form-group`/`pv-form-label`/`pv-form-control`/`pv-form-help`/`pv-form-actions`.
- [ ] Для специфичных элементов, у которых нет готового аналога, **определить классы в `app.css`**
      (или переиспользовать существующие):
      - выбор сегмента (`pv-segment-choices`/`-choice`/`-label`/`-title`/`-desc`) — радио-карточки
        получателей (рамка, выделение выбранного, заголовок + описание);
      - предпросмотр сообщения (`pv-broadcast-preview` + `pv-bubble`) — «пузырь» как в мессенджере.
      Выбрать один подход (переиспользовать vs новые классы) и зафиксировать в отчёте/ADR-0005.
- [ ] HTMX-превью числа получателей и счётчик символов остаются рабочими (не сломать `_preview_count`).
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные (шаблон не ломает smoke-тесты админки).
- [ ] PR открыт `TASK-095: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] **После выката** — открыть `/broadcasts/new` в браузере: форма оформлена (поля, сегменты,
      предпросмотр, кнопки), не «голый HTML». Зафиксировать в отчёте.
- [ ] Отчёт `handoff/outbox/TASK-095-report.md` написан.
- [ ] **Move-семантика inbox→archive** — оставить директорию `handoff/archive/TASK-095-<slug>/task.md`,
      без залипших `.in-progress`. Приёмка — по `git diff`/живому прогону, не по тексту отчёта.

## Артефакты

- `* src/admin/templates/broadcasts/form.html` — перевод на классы дизайн-системы
- `* src/admin/static/css/app.css` — при необходимости: `pv-segment-*`, `pv-broadcast-preview`/`pv-bubble`
- `* docs/adr/0005-admin-v2-stack.md` — фиксация решения (если вводятся новые классы)

## Мелочь (можно сюда же, опционально)

- Активная вкладка карточки события («Данные») сейчас красным **текстом**. По спеке 088 хотелось
  тёмный текст `--pv-fg` + подчёркивание `--pv-accent`. Подчёркивание (accent) ок; текст — причесать
  на `--pv-fg`, если не решено оставить акцентным.

## Подсказки исполнителю

- Эталон — `categories/form.html` (рендерится корректно): скопировать паттерн полей оттуда.
- `parallel-safe: true` — изолировано в модуле рассылок; с остальным не пересекается. После 094
  (cache-busting) уже в проде, так что новые стили подхватятся без hard-reload.
