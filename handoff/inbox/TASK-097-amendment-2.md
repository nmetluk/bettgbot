---
amends: TASK-097
created: 2026-06-01
author: cowork-agent
status: rework-requested
supersedes-status-of: TASK-097-amendment.md (Дефект 1 закрыт частично)
---

# TASK-097 — дополнение №2 (один оставшийся пункт + как влить)

Повторное ревью ветки `feature/TASK-097-admin-stats-bot-digest` (коммит `cfbbcda`) против `origin/main`.

## Что уже закрыто (amendment №1)

- ✅ Дефект 2 (handoff): cowork убрал inbox-копии задачи/amendment из main, спеки влиты (#193). На твоей ветке `archive/TASK-097-…/{task.md, amendment.md}` + `outbox/report` — дубля inbox↔archive больше не будет.
- ✅ Дефект 1, data-слой: добавлены integration-тесты на `StatsService.event_result_summary` и дайджест-агрегаты (`test_stats_service.py`).

## Что осталось (блокер закрытия)

### 1. Тесты ДЖОБОВ с замоканным `Bot` (не сервиса — он покрыт)

- [ ] `dispatch_event_result_notifications`:
  - пустой `ADMIN_TELEGRAM_CHAT_IDS` → не шлёт и **НЕ** ставит `result_notified_at` (события не трогаются);
  - нормальный путь → `send_message`/`send_document` во все chat_id + `result_notified_at` проставлен;
  - **повторный тик → второй раз не шлёт** (идемпотентность по `result_notified_at IS NULL`);
  - 0 угадавших → `send_document` **не** вызывается (CSV не прикладывается), в тексте «✅ Угадали: 0».
- [ ] `send_daily_admin_digest`:
  - пустой список → не шлёт, не падает;
  - заполненный → `send_message` на каждый chat_id; цифры окна 24ч корректны.
- [ ] `tests/unit/bot/scheduler/test_builder.py` — проверить регистрацию обоих новых джобов (id, триггеры; у дайджеста `timezone="Europe/Moscow"`, у нотификаций `IntervalTrigger(minutes=1)`).

### 2. Влить ветку (почему сейчас не вливается)

- [ ] **Перебазировать `feature/TASK-097` на свежий `origin/main`.** Ветка отстала от main; `chore/handoff-097` не уходила в auto-merge именно из-за устаревшей базы (branch protection «require branches up to date») — после rebase влилась. Тот же фикс нужен коду.
- [ ] Зелёные `ruff` / `mypy src/shared` / весь `pytest` с новыми тестами.
- [ ] `outbox/TASK-097-report.md` — обновить по факту: число добавленных тестов, что покрыто (приёмка по `git diff --stat`, не по слову «done»).
- [ ] Перед archive-коммитом: `ls handoff/inbox/ | grep TASK-097` = пусто (cowork уже вычистил main; на твоей ветке inbox-копий быть не должно).
- [ ] Открыть/обновить PR → `gh pr merge --auto --squash` → **убедиться в GitHub Actions, что CI зелёный и PR реально встал в auto-merge** (не просто «запушено»).

`docs/`/`state/` не трогать — уже в main (#193).

## Условие закрытия

Чекбоксы выше + исходный DoD. После — обычный цикл: зелёный CI, правдивый отчёт, один экземпляр в `archive`, inbox без orphan, PR влит в `main`.
