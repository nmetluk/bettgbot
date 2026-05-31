---
id: TASK-086
created: 2026-05-31
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - src/bot/scheduler/jobs.py
  - src/shared/repositories/reminder_dispatch_log.py
  - docs/audit/2026-05-31-full-audit.md
priority: normal
estimate: S
---

# TASK-086: dispatch_reminders — crash-safe commit-границы (без дублей напоминаний при рестарте)

## Контекст

Аудит `docs/audit/2026-05-31-full-audit.md` (находка **M2**, перенесена из аудита
`2026-05-30` — предложенный тогда TASK-065 не был заведён).

Факт по коду (`origin/main` @ `08adb25`), `src/bot/scheduler/jobs.py`:

- `dispatch_reminders` корректно делает идемпотентность через порядок: `dispatch_log.record(...)`
  зовётся **до** `bot.send_message(...)` (строки ~`:50-60`).
- **Но** `session.commit()` — единственный, в самом конце цикла (~`:85`). Весь батч —
  одна транзакция.
- Класс бага: если бот падает/рестартится в середине батча, незакоммиченная транзакция
  откатывается → строки `reminder_dispatch_log` пропадают → на рестарте те же напоминания
  попадают в `find_candidates` снова и **отправляются повторно**.

Эталон рядом — `dispatch_broadcasts` (тот же файл) уже сделан crash-safe: батчевые commit'ы
с `commit_batch_size` (строки ~`:151,167,219-225`). Этот же приём чинил restart-дубли для
рассылок в amendment TASK-061.

Импакт ниже, чем у рассылок (батч напоминаний ограничен `window_minutes`), но для пользователя
дубль напоминания — заметный дефект, и первопричина идентична.

## Цель

Перезапуск бота в середине окна доставки напоминаний больше не приводит к повторной отправке
уже доставленных напоминаний: запись в `reminder_dispatch_log` фиксируется (commit) до краша,
а не теряется при откате общей транзакции.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-086-report.md`.** Без отчёта CI handoff-consistency красный,
> PR не мёрджится. Шаблон — `handoff/templates/report.md`.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен.

- [ ] `dispatch_reminders` фиксирует доставку инкрементально — commit записи лога до/сразу
      после `send_message`, по-элементно или порциями (`commit_batch_size`), по образцу
      `dispatch_broadcasts` в том же файле. Идемпотентный порядок `record` → `send` сохранён.
- [ ] Сохранена существующая семантика: `record` через `ON CONFLICT DO NOTHING` (гонки),
      `TelegramAPIError`/блок пользователя не валит весь батч.
- [ ] Integration-тест (реальный Postgres): симулируется «отправлено N, затем краш до конца
      батча» → после повторного прогона `dispatch_reminders` уже доставленные напоминания
      **не** отправляются повторно (счётчик `send_message`/моков не растёт по дубликатам).
      Тест **падал бы** на текущем single-commit коде.
- [ ] `ruff check` чист, `mypy src/shared src/bot` зелёный, `pytest` зелёный.
- [ ] PR открыт, имя `TASK-086: <subject>`, CI зелёный, PR смёрджен, локальная `main` синхронизирована.
- [ ] Отчёт `handoff/outbox/TASK-086-report.md` написан.
- [ ] **Move-семантика inbox→archive** (см. `handoff/README.md`).

## Артефакты

- `* src/bot/scheduler/jobs.py` — commit-границы в `dispatch_reminders`
- `+ tests/integration/...` — регресс на restart-дубли (или расширение существующего теста job'а)

## Ссылки

- Аудит: [`docs/audit/2026-05-31-full-audit.md`](../../docs/audit/2026-05-31-full-audit.md) (M2)
- Эталон crash-safe: `dispatch_broadcasts` в `src/bot/scheduler/jobs.py`
- Прецедент: amendment TASK-061 (restart-дубли рассылок)

## Подсказки исполнителю

Не меняй контракт идемпотентности (`record` строго ДО `send_message`) — меняется только
**где стоят commit-границы**. Аккуратно с тем, что `find_candidates` — один SQL: при
порционных commit'ах убедись, что курсор/выборка кандидатов материализована до начала
отправок (иначе commit в середине может повлиять на ленивую выборку).
