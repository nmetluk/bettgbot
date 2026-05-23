---
id: TASK-014
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - src/shared/services/prediction.py
  - src/shared/services/stats.py
  - src/bot/routers/events.py
priority: high
estimate: L
---

# TASK-014: раздел «📋 Мои прогнозы» — активные / архив + статистика

## Контекст

Четвёртый реальный handler. Пользователь открывает «📋 Мои прогнозы» (или `/my`), видит две вкладки «🟢 Активные» / «📦 Архив», тапает прогноз → карточка события. Под архивом — статистика `📊 {correct}/{total} ({percent}%)`. FSM не нужен. Использует `@require_active_user`. Серверная логика готова (`PredictionService.list_*_by_user`, `StatsService.user_stats`).

## Definition of Done

### Step 1 — Расширение `render_event_card` параметром `back_button`

- Сигнатура `event_card_kbd`: `back_category_id: int | None` → `back_button: tuple[str, CallbackData]`. Передаётся «текст кнопки» + готовый `CallbackData`.
- `render_event_card(query, event_id, back_button, user, session)` обновлён.
- Существующие вызовы (`on_event` в events.py, `on_predict_cancel` в prediction.py) передают `("🔙 К событиям", CategoryCb(category_id=..., page=0))`.

### Step 2 — Callback-data

- `MyTab = Literal["active", "archive"]`.
- `MyTabCb(tab, page=0)` prefix `"m"` — таб + пагинация.
- `MyPredictionCb(event_id, tab)` prefix `"mp"` — тап на прогноз, `tab` для возврата.

### Step 3 — Клавиатуры

- `my_predictions_kbd(predictions, *, tab, page, has_prev, has_next)`:
  - 1 кнопка на прогноз (callback `MyPredictionCb`).
  - Ряд табов: текущий с маркером `✓`.
  - Пагинация `‹/›` если `has_prev`/`has_next`.
- Inline-кнопка «🔙 В меню» **не нужна** — есть постоянный ReplyKeyboard главного меню.

### Step 4 — Router `src/bot/routers/my.py`

- `cmd_my` (Command + F.text) → первичный рендер активной вкладки.
- `on_my_tab` (MyTabCb) → переключение / пагинация через `edit_text`.
- `on_my_prediction` (MyPredictionCb) → `render_event_card` с `back_button=("🔙 К моим прогнозам", MyTabCb(tab=..., page=0))`.
- `PAGE_SIZE = 7` локально (как в events.py).
- Helper `_build_my_view(user, session, tab, page) → (text, kbd)` — переиспользуется в `cmd_my` и `on_my_tab`.

### Step 5 — Тексты

7 новых констант: `MY_HEADER_ACTIVE`, `MY_HEADER_ARCHIVE`, `MY_NO_ACTIVE`, `MY_NO_ARCHIVE`, `MY_ROW_ACTIVE` (title/starts_at/outcome/close_at), `MY_ROW_ARCHIVE` (title/status_emoji/starts_at/outcome/result_label), `MY_STATS` (correct/total/percent).

### Step 6 — Тесты

`tests/unit/bot/routers/test_my_handler.py` — ~10 mock-based тестов:
- `cmd_my`: unauth, blocked, no_predictions, lists_active.
- `on_my_tab`: switch_to_archive_renders_stats, archive_empty, pagination.
- `on_my_prediction`: calls_render_event_card_with_back_to_my.

Регрессия `test_events_handler.py` + `test_prediction_handler.py` под новый `back_button`.

### Качество

- mypy, ruff, pytest зелёные.
- PR в main, отчёт в outbox, задача в archive.

## Подсказки

- **N+1 при подгрузке `outcome` для строки прогноза:** дёргать `EventService.get_event(event_id, with_outcomes=True)` на каждый элемент. PAGE_SIZE=7 → 7 запросов. На MVP приемлемо. Если в review увидим горячую точку — добавим `list_*_by_user_with_relations` в репозиторий.
- **Маркер активного таба:** unicode `✓` в тексте кнопки. Жирность в кнопках Telegram нет.
- **Mock `render_event_card`:** `monkeypatch.setattr("src.bot.routers.my.render_event_card", AsyncMock())` — патчь на пути импорта.
- **Defensive UX для архива:** если `result_outcome_id is None` (admin заархивировал без фиксации, либо automation TASK-018) → `status_emoji = "⏳"`, `result_label = "—"`.

> Полный исходник с code-snippets, alternatives и подсказками — в `nmetluk/bettgbot:handoff/inbox/TASK-014-my-predictions.md`. Этот файл в Drive — короткий снапшот для контекста.
