---
id: TASK-089
created: 2026-05-31
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/routes/broadcasts.py
  - src/admin/templates/broadcasts/form.html
  - src/admin/templates/broadcasts/_preview_count.html
priority: high
estimate: S
---

# TASK-089: Починить форму создания рассылки — `/broadcasts/new` отдаёт HTTP 500

## Контекст

Живой прогон админки на проде `a.pinbetting.ru` (2026-05-31, cowork-аудит) показал: кнопка
«Новая рассылка» на `/broadcasts` ведёт на `/broadcasts/new`, который возвращает белую
страницу `Internal Server Error`. Подтверждено статусом ответа:

```
GET https://a.pinbetting.ru/broadcasts/new  →  500
```

Список рассылок (`/broadcasts`) при этом открывается нормально (пустой, «Ещё ни одной
рассылки не было»). Падает именно рендер формы создания. Из-за этого **весь функционал
рассылок недоступен**, и дизайн-находки по рассылкам (алерт/прогресс/бейджи — C2/C4/C5 в
[TASK-088](TASK-088-design-conformance-to-mockup.md)) нельзя проверить вживую, пока форма не
откроется.

## Цель

`GET /broadcasts/new` отдаёт 200 и рендерит рабочую форму создания рассылки (включая
HTMX-превью числа получателей), без 500.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-089-report.md`.** Без отчёта CI handoff-consistency красный,
> PR не мёрджится.

- [ ] Воспроизвести 500 локально (`make` dev / uvicorn), снять полный traceback из логов.
- [ ] Найти и устранить корневую причину в `src/admin/routes/broadcasts.py` и/или
      `templates/broadcasts/form.html` / `_preview_count.html` (типичные кандидаты: обращение к
      незаполненной переменной шаблона, отсутствующий контекст, падающий запрос к БД/сервису,
      несоответствие сигнатуры зависимости).
- [ ] `GET /broadcasts/new` → 200, форма рендерится; HTMX-превью получателей (`_preview_count`)
      отвечает без ошибок.
- [ ] Регрессионный тест: добавить/расширить тест на `GET /broadcasts/new` (ожидаемый 200), чтобы
      500 не вернулся незаметно. Если в админке есть smoke-набор маршрутов — включить туда.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные.
- [ ] PR открыт `TASK-089: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] Отчёт `handoff/outbox/TASK-089-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`).

## Артефакты

- `* src/admin/routes/broadcasts.py` — вероятное место падения (handler `GET /broadcasts/new`)
- `* src/admin/templates/broadcasts/form.html` — рендер формы
- `* src/admin/templates/broadcasts/_preview_count.html` — HTMX-превью получателей
- `* tests/...` — регрессионный тест на маршрут

## Подсказки исполнителю

- Это **серверный** 500, не клиент: смотреть traceback приложения, не консоль браузера.
- Список `/broadcasts` работает, падает только `/broadcasts/new` — значит проблема в коде формы
  (контекст/шаблон/зависимость), а не в подключении к БД в целом.
- Не путать с дизайн-задачей: здесь чиним работоспособность, не верстку. Косметика рассылок
  (алерт/прогресс/бейджи) — в [TASK-088](TASK-088-design-conformance-to-mockup.md).
- `parallel-safe: true` — задача изолирована в модуле рассылок, не пересекается с CSS/оболочкой
  из TASK-088/090/091.
