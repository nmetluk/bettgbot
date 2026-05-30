---
id: TASK-080
created: 2026-05-30
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - .github/workflows/handoff-consistency.yml
  - handoff/README.md
priority: normal
estimate: XS
---

# TASK-080: handoff-consistency должен краснеть на transient-суффиксах в inbox на main

## Контекст

`TASK-076.in-progress.md` пролежал в `handoff/inbox/` на `main` уже ПОСЛЕ того, как код 076 был
влит — то есть рабочее (transient) состояние задачи утекло в main, и `handoff-consistency` это
не поймал. Суффиксы `.in-progress` / `.blocked` — это переходные состояния жизненного цикла
(см. CLAUDE.md), они не должны существовать в `main`: к моменту merge задача либо открыта
(`TASK-NNN-slug.md`), либо закрыта (в `archive/`).

## Цель

Добавить в CI-проверку инвариант: на `main` в `handoff/inbox/` нет файлов с transient-суффиксами.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-080-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

- [ ] В `.github/workflows/handoff-consistency.yml` добавить шаг/проверку: если существует любой
      `handoff/inbox/TASK-*.in-progress.md` или `handoff/inbox/TASK-*.blocked.md` — упасть с понятным
      сообщением (какой файл, что должно быть вместо: открытая задача `TASK-NNN-slug.md` или archive).
      Стиль — как у существующих проверок в этом workflow (`set -euo pipefail`, счётчик `violations`).
- [ ] Не ломать остальные проверки; формат вывода консистентен с текущими (✓/❌).
- [ ] (опц.) Дописать в `handoff/README.md` строку, что transient-суффиксы в `main` запрещены и
      ловятся CI. README — артефакт проектировщика; правку README делать ТОЛЬКО в рамках этой задачи,
      она явно разрешена здесь.
- [ ] Проверить локально: на текущем чистом inbox — зелено; искусственно создав
      `handoff/inbox/TASK-999.in-progress.md` — красно (привести вывод в отчёт, временный файл удалить).
- [ ] PR `TASK-080: handoff-consistency guards transient inbox suffixes`; auto-merge по зелёному CI;
      `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Вне скоупа

- Менять move-семантику или другие инварианты handoff. Только новая проверка на transient-суффиксы.
- Делать проверку «код влит ⇒ задача заархивирована» — CI не знает о merge-статусе, это вне его.

## Артефакты

- `* .github/workflows/handoff-consistency.yml` — новая проверка
- `* (опц.) handoff/README.md` — строка про transient-суффиксы
- `* handoff/outbox/TASK-080-report.md`

## Ссылки

- Прецедент: `TASK-076.in-progress.md` завис в inbox на main после merge кода 076
- Существующие проверки: `.github/workflows/handoff-consistency.yml`
