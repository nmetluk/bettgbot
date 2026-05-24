# Brief — task-014-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-014 и подготовить TASK-015.

## Контекст

Локальный CC закрыл TASK-014 за 1 коммит (squash `81ec4ca`). Раздел «📋 Мои прогнозы» работает: `cmd_my` (Command + F.text) с дефолтной активной вкладкой, `on_my_tab` для переключения «🟢 Активные / 📦 Архив» и пагинации (`PAGE_SIZE=7`), `on_my_prediction` → `render_event_card` с кнопкой «🔙 К моим прогнозам». В архиве — `MY_STATS` через `StatsService.user_stats`. Рефакторинг helper'а `render_event_card` под `back_button: tuple[str, CallbackData]` + новый параметр `allow_archived: bool = False` (карточка архивного события показывается только при заходе из «Мои прогнозы → Архив», из каталога не показывается — защита от гонки). 10 новых тестов (всего 105 unit, ~1ч на выполнение).

Полный отчёт — [`handoff/outbox/TASK-014-report.md`](../../handoff/outbox/TASK-014-report.md).

PR [#37](https://github.com/nmetluk/bettgbot/pull/37) → squash `81ec4ca`. Archive PR [#38](https://github.com/nmetluk/bettgbot/pull/38) → `5097491`.

## Что необычного в этом цикле

**Локальный CC выполнял задачу на удалённой машине** — взял TASK-014 не из репо (там его не было — мои правки лежат только в локальной Cowork-сессии и до origin не доходили), а **из Google Drive backup** через зеркало, которое я залил в прошлый раз через MCP-коннектор. **Это первая фактическая проверка двух-машинного workflow** — он работает: Drive послужил каналом передачи задачи, удалённый CC выполнил, запушил в origin/main.

Побочный эффект: **pre-task cleanup PR не был сделан** на удалённой машине — у неё working tree был чистый (мои правки она не видела). Это нормально для этого конкретного цикла, но означает, что мои накопленные правки (`state/PROJECT_STATUS.md`, `state/DECISIONS.md`, `handoff/README.md` Drive-секция, `sessions/2026-05-23-12-task-013-review/`, `handoff/inbox/TASK-014-my-predictions.md`) до сих пор живут **только в моей локальной Cowork-сессии**. Их подхватит локальный CC на этой машине при следующем pre-task cleanup PR перед TASK-015.

Дополнительно — нужно **удалить устаревший** `handoff/inbox/TASK-014-my-predictions.md` (он уже в `handoff/archive/`, дубликат). Я sandbox-том удалять файлы не могу, поэтому в TASK-015 явно прописал шаг для локального CC.

## Что сделано в этой сессии

- Приняты решения по пяти открытым вопросам — **все «keep»**:
  - Back-через-FSM-прогноза (отмена «Изменить прогноз» из «Мои прогнозы» возвращает в категорию) — keep как MVP, фиксируем как **тех-долг** в BACKLOG. «Правильное» решение (расширение трёх prediction CB-классов полем `back_my_tab` или хранение back в FSM-data) дороже, чем потеря UX.
  - Эмодзи статуса в кнопке прогноза — keep как title-only. `status_emoji` уже есть в тексте под кнопкой.
  - Маркер `✓` активного таба — keep, явный визуальный сигнал.
  - `allow_archived` параметр в `render_event_card` — keep. Хорошее ad-hoc решение: явный whitelist для входа из архива, защита от гонки в каталоге.
  - Регресс-тесты на `back_button` — keep как есть. Тесты прошли без правок (они не лезут в детали клавиатуры), добавлять явные = тестировать код вместо поведения.
- Обновлён [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (закрытие TASK-014, новый «Следующий шаг» TASK-015).
- Добавлены 3 строки в [`state/DECISIONS.md`](../../state/DECISIONS.md): `back_button: tuple[str, CallbackData]`, `allow_archived` параметр, back-target FSM как тех-долг.
- Зафиксирован **тех-долг в [`state/BACKLOG.md`](../../state/BACKLOG.md)**: «back-target после FSM прогноза, если зашли из "Мои прогнозы"».
- Сформирована задача [`handoff/inbox/TASK-015-reminders.md`](../../handoff/inbox/TASK-015-reminders.md) — настройка напоминаний (FSM `EditingReminders`, пресеты + свой ввод).
- Зеркало в Drive обновлено: новая сессия, TASK-015, обновлённые state, новый memory-export.

## Следующие шаги

1. Владелец запускает локальный Claude Code (на этой машине) на TASK-015. **Pre-task cleanup PR обязателен**: вынести в `chore/post-TASK-014-cowork-cleanup` все накопленные правки cowork (state, sessions, README), плюс удалить через `git add/rm` дубликат `handoff/inbox/TASK-014-my-predictions.md`.
2. После TASK-015 — TASK-016 (`/help`, статический текст уже готов с TASK-010).
3. После TASK-016 — TASK-017 (APScheduler: рассылка напоминаний). Это первая фоновая задача — потребует расширения `src/bot/scheduler/`.

## Замечания на будущее

- **Двухмашинный workflow через Drive работает**, но локальный CC на машине-исполнителе должен помнить, что **pre-task cleanup PR может быть пустым** (если на этой машине ничего не менялось от cowork). Это нормально — ритуал по `CLAUDE.md` остаётся, но коммит не появится.
- **Метрика тестов** в отчётах исполнителей считается по-разному: «105 unit» в TASK-014 vs «170 всего» в TASK-013. Не критично, но желательно унифицировать формат («N unit + N integration» вместо одного числа). Запишу в подсказке для будущих отчётов.
