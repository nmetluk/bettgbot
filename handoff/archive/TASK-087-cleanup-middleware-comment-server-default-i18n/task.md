---
id: TASK-087
created: 2026-05-31
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/app.py
  - src/shared/models/broadcast.py
  - src/shared/models/broadcast_delivery.py
  - src/bot/routers/events.py
  - src/bot/texts.py
  - docs/audit/2026-05-31-full-audit.md
priority: low
estimate: S
---

# TASK-087: Cleanup — комментарий middleware-ordering, func.now() в broadcast-моделях, вынос строк в texts.py

## Контекст

Аудит `docs/audit/2026-05-31-full-audit.md` — три Low-находки (L1, L2, L3), перенесённые
из аудита `2026-05-30`. Мелкие, не блокируют релиз, удобно закрыть одним cleanup-PR.

## Цель

Закрыть L1–L3: убрать вводящий в заблуждение комментарий о порядке middleware, привести
`server_default` broadcast-моделей к общей конвенции, централизовать два захардкоженных текста бота.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-087-report.md`.** Без отчёта CI handoff-consistency красный,
> PR не мёрджится. Шаблон — `handoff/templates/report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен.

**L1 — комментарий о порядке middleware (`src/admin/app.py:123-131`):**

- [ ] Исправить комментарий: в Starlette `add_middleware` делает outermost **последний**
      добавленный (`SecurityHeadersMiddleware`), а `ProxyHeadersMiddleware` (добавлен первым) —
      innermost. Комментарий должен отражать реальный порядок выполнения.
- [ ] (Опционально, на усмотрение исполнителя — если делаешь, опиши в отчёте) убрать
      дублирующий app-level `ProxyHeadersMiddleware`, т.к. схему уже правит uvicorn
      `--proxy-headers` на уровне сервера; **либо** поставить его действительно outermost,
      если на него где-то полагаются. Если не уверен — оставь только правку комментария.

**L2 — `server_default` в broadcast-моделях:**

- [ ] `src/shared/models/broadcast.py:60` — `server_default="now()"` → `server_default=func.now()`.
- [ ] `src/shared/models/broadcast_delivery.py:32` — то же.
- [ ] DDL не меняется (рантайм-default уже задан миграцией `0005`); новая миграция **не нужна**.
      Цель — единообразие с остальными 11 моделями и безопасность autogenerate.

**L3 — вынос строк бота в `texts.py`:**

- [ ] `src/bot/routers/events.py:100` — `f"<b>{category_name}</b> — страница {page+1}"` →
      шаблон в `src/bot/texts.py`, подстановка через `safe_format`.
- [ ] `src/bot/routers/events.py:156` — `f"\n\n✅ Ваш прогноз: «{chosen.label}»"` → то же.
- [ ] `git grep` по этим строкам в роутере → пусто (текст только в `texts.py`).

**Общее:**

- [ ] `ruff check` чист, `ruff format --check` чист, `mypy src/shared src/bot src/admin` зелёный,
      `pytest` зелёный (существующие тесты events-роутера обновлены под новые тексты, если
      они проверяют точные строки).
- [ ] PR открыт, имя `TASK-087: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] Отчёт `handoff/outbox/TASK-087-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`).

## Артефакты

- `* src/admin/app.py` — комментарий (+опц. middleware)
- `* src/shared/models/broadcast.py` — `func.now()`
- `* src/shared/models/broadcast_delivery.py` — `func.now()`
- `* src/bot/routers/events.py` — вынос 2 строк
- `* src/bot/texts.py` — 2 новых текста
- `* tests/...` — если тесты проверяют точные строки events-роутера

## Ссылки

- Аудит: [`docs/audit/2026-05-31-full-audit.md`](../../docs/audit/2026-05-31-full-audit.md) (L1, L2, L3)
- Конвенции: [`docs/08-conventions.md`](../../docs/08-conventions.md) (i18n через `texts.py`)

## Подсказки исполнителю

`parallel-safe: true` — можно брать параллельно с другой parallel-safe задачей. Три правки
независимы; если по L1 решишь трогать сам middleware (а не только комментарий) — это
единственное место с поведенческим риском, опиши решение в отчёте.
