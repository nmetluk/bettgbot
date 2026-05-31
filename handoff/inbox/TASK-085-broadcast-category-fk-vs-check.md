---
id: TASK-085
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/shared/models/broadcast.py
  - src/migrations/versions/0005_broadcasts.py
  - src/shared/services/category.py
  - docs/03-data-model.md
  - docs/audit/2026-05-31-full-audit.md
priority: normal
estimate: M
---

# TASK-085: Согласовать broadcast.category_id FK и CHECK (целостность при удалении категории)

## Контекст

Аудит `docs/audit/2026-05-31-full-audit.md` (находка **M1**, перенесена ещё из аудита
`2026-05-30` — предложенный тогда TASK-064 так и не был заведён).

Факт по коду (`origin/main` @ `08adb25`):

- `src/shared/models/broadcast.py:44` — FK `category_id` объявлен с `ondelete="SET NULL"`.
- `src/shared/models/broadcast.py:75-76` — CHECK:
  `(segment = 'category' AND category_id IS NOT NULL) OR (segment != 'category')`.
- То же в миграции `src/migrations/versions/0005_broadcasts.py:70-98`.

Конфликт: если удалить категорию, на которую ссылается рассылка с `segment='category'`,
БД попытается выставить `category_id=NULL` (по `SET NULL`) → это нарушит CHECK → `DELETE`
категории упадёт с невнятной constraint-ошибкой на уровне Postgres, а не осмысленной
доменной ошибкой.

Сейчас удаление категории идёт через `CategoryService` (см. `CategoryHasEventsError` и т.п.) —
там уже есть паттерн перевода `IntegrityError` в доменные исключения, но связь
broadcast↔category в этот контракт не заведена.

## Цель

Удаление категории при наличии связанных рассылок ведёт себя предсказуемо: либо явно
запрещено с понятной доменной ошибкой, либо исторические рассылки переживают удаление
категории без нарушения инвариантов. Поведение зафиксировано в `docs/03-data-model.md`.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-085-report.md`.** Без отчёта CI handoff-consistency красный,
> PR не мёрджится. Шаблон — `handoff/templates/report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен.

Выбрать **один** из двух вариантов (обосновать выбор в отчёте); если видишь третий лучший —
оформи `handoff/outbox/TASK-085-question.md` и не угадывай:

**Вариант A — RESTRICT (запрет удаления, рекомендуемый по умолчанию):**

- [ ] FK `category_id` → `ondelete="RESTRICT"` в модели `broadcast.py` и в новой миграции
      (`0006_*`), которая `ALTER`-ит существующий constraint (drop + create).
- [ ] `CategoryService.delete` ловит соответствующий `IntegrityError` и поднимает новую
      доменную ошибку (напр. `CategoryHasBroadcastsError`) — exhaustive, по образцу
      существующих `Category*Error` (см. `src/shared/exceptions.py`).
- [ ] Admin-handler удаления категории показывает осмысленный alert/409 вместо 500.
- [ ] CHECK остаётся как есть (инвариант `segment='category' ⇒ category_id NOT NULL` валиден).

**Вариант B — снимок сегмента (исторические рассылки переживают удаление):**

- [ ] Хранить человекочитаемый снимок цели рассылки (напр. `segment_label`/`category_name`
      на момент отправки), чтобы FK `category_id` мог стать `NULL` без потери смысла.
- [ ] Релаксировать CHECK так, чтобы `category_id IS NULL` допускался для завершённых
      (`status='sent'`/архивных) рассылок, но требовался при создании новой `segment='category'`.
- [ ] Миграция `0006_*` + синхронизация модели.

Общее для обоих вариантов:

- [ ] Обновлён `docs/03-data-model.md` — раздел про broadcast: зафиксировано выбранное
      поведение и причина.
- [ ] Integration-тест на реальном Postgres: удаление категории со связанной
      `segment='category'`-рассылкой ведёт себя по выбранному контракту (RESTRICT → доменная
      ошибка / Вариант B → `category_id=NULL` без нарушения CHECK).
- [ ] Миграция применяется и откатывается (`make db.up` / `db.down`) без ошибок.
- [ ] `ruff check` чист, `mypy src/shared` зелёный, `pytest` зелёный.
- [ ] PR открыт, имя `TASK-085: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] Отчёт `handoff/outbox/TASK-085-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`).

## Артефакты

- `* src/shared/models/broadcast.py` — FK ondelete и/или CHECK
- `+ src/migrations/versions/0006_broadcast_category_integrity.py` — новая миграция
- `* src/shared/services/category.py` — обработка удаления (Вариант A)
- `* src/shared/exceptions.py` — новая доменная ошибка (Вариант A)
- `* docs/03-data-model.md` — фиксация поведения
- `+ tests/integration/...` — регресс на удаление категории

## Ссылки

- Аудит: [`docs/audit/2026-05-31-full-audit.md`](../../docs/audit/2026-05-31-full-audit.md) (M1)
- Модель данных: [`docs/03-data-model.md`](../../docs/03-data-model.md)

## Подсказки исполнителю

`docs/03-data-model.md` — зона проектировщика, но эта задача **явно** разрешает его правку
(зафиксировать решение). Перед изменением CHECK сверь фрагмент с инвариантами `docs/03`
(правило проекта после блокировки TASK-018). Прецедент релакса инварианта через миграцию —
`0003_relax_event_archive_constraint`.
