---
amends: TASK-097
created: 2026-06-01
author: cowork-agent
status: rework-requested
---

# TASK-097 — дополнение (возврат на доработку)

Ревью ветки `feature/TASK-097-admin-stats-bot-digest` (коммит `2d72e7d`) **против `origin/main`**, не по отчёту. Реализация **в основном корректная** — переписывать рабочий код не нужно, нужно закрыть пробелы ниже. Принять задачу нельзя, пока не выполнены условия закрытия.

## Что сделано хорошо (не трогать)

- Миграция `0007_event_result_notified_at` (up/down корректны, в CHECK-инвариант не лезет).
- `Settings.admin_telegram_chat_ids` (`NoDecode` + валидатор парсинга CSV).
- Дайджест-джоб на `CronTrigger(hour=16, minute=0, timezone="Europe/Moscow")`; глобальный scheduler остался UTC — верно.
- `dispatch_event_result_notifications`: `with_for_update(skip_locked=True)`, `result_notified_at=utcnow()` per-event после отправки — идемпотентно.
- Пустой `ADMIN_TELEGRAM_CHAT_IDS` → `warning` + return, БД не трогается (оба джоба).
- CSV через `send_document`, ошибка отправки в один чат → warning + продолжение.

## Дефект 1 (блокер) — дыра в тестах vs DoD

На ветке добавлены только `tests/unit/bot/test_csv.py` и `tests/unit/test_config.py`. DoD требовал больше; `tests/integration/services/test_stats_service.py` **не тронут**. Не покрыта вся бизнес-логика. Требуется добавить:

- [ ] integration на `StatsService.event_result_summary(event_id)`: фикстура с несколькими пользователями и разными исходами — проверить `total_predictions`, `correct_count`, `outcome_distribution` (counts + флаг победителя), состав `correct_users`.
- [ ] integration на дайджест-агрегаты: «новых за 24ч» (новый vs старый `created_at`), «прогнозов за 24ч», «всего пользователей» — граничные значения окна.
- [ ] тесты обоих джобов с **замоканным `Bot`**:
  - пустой `ADMIN_TELEGRAM_CHAT_IDS` → не шлёт и не меняет БД (нет `result_notified_at`);
  - после отправки `result_notified_at` проставлен; **повторный тик не шлёт повторно** (idempotency);
  - 0 угадавших → текст со «✅ Угадали: 0», CSV **не** прикладывается;
  - дайджест зовёт `send_message` на каждый chat_id из списка.

## Дефект 2 (блокер) — несогласованный handoff (риск inbox-orphan)

Ветка `feature/...` несёт `handoff/archive/TASK-097-.../task.md` + `handoff/outbox/TASK-097-report.md`, но **не убирает** inbox-копию (задача и это дополнение лежат в `handoff/inbox/` через ветку спек). Если влить и спеки, и feature-ветку — в `main` окажутся **одновременно** `inbox/TASK-097-*` и `archive/TASK-097-*` → CI `handoff-consistency` красный (inbox-orphan; ровно повторяющаяся в проекте ошибка).

Требуется в финальном код-PR:

- [ ] `git rm` обеих inbox-копий: `TASK-097-admin-stats-bot-digest.md` **и** `TASK-097-amendment.md`.
- [ ] В `archive/TASK-097-admin-stats-bot-digest/` оставить `task.md` (+ положить туда же `amendment.md`). Отчёт — в `outbox` или archive.
- [ ] Перед archive-коммитом: `ls handoff/inbox/ | grep TASK-097` = пусто.
- [ ] Слить **сначала** ветку спек `chore/handoff-097` (docs 04/05/03 + DECISIONS + задача), затем код-PR с move inbox→archive — иначе move нечего удалять.

## Дефект 3 — отчёт и merge

- [ ] Переписать `outbox/TASK-097-report.md` по факту: явно указать число добавленных тестов и что покрыто. Приёмка идёт по `git diff --stat` и живому прогону, не по формулировке «done».
- [ ] Код-PR мёрджить **только** после зелёного CI с новыми тестами; включить `gh pr merge --auto --squash`. Сейчас ни один PR (specs/feature) в `main` не влит — проверить в GitHub Actions, почему (CI/право auto-merge), и довести до зелёного.

## Условие закрытия

Все чекбоксы Дефектов 1–3 + исходный DoD TASK-097. После доработки — обычный цикл: зелёный CI, отчёт, один экземпляр в archive, inbox без orphan.
