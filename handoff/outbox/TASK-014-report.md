---
task: TASK-014
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/37
branch: feature/TASK-014-my-predictions
commits:
  - 81ec4ca TASK-014: handler «📋 Мои прогнозы» — активные/архив + статистика (squash)
---

# Отчёт по TASK-014: раздел «📋 Мои прогнозы» — активные / архив + статистика

## Сводка

Четвёртый реальный handler. Пользователь открывает «📋 Мои прогнозы» (или
`/my`), видит вкладку «🟢 Активные» по умолчанию; кнопкой переключается на
«📦 Архив», где дополнительно показывается строка статистики. Тап на конкретный
прогноз → `render_event_card` с кнопкой «🔙 К моим прогнозам».

Внутренне сделано:

- **Step 1 — рефакторинг `render_event_card`.** Сигнатура `event_card_kbd` и
  `render_event_card` обобщена: `back_category_id` заменён на `back_button:
  tuple[str, CallbackData]`. Это позволяет каждой входной точке (каталог,
  отмена FSM, «Мои прогнозы») собирать свою кнопку «Назад» без знания о других
  сценариях. `PredictStartCb` остаётся со скаляром `back_category_id` — в
  `event_card_kbd` для предик-кнопки пробрасываем `event.category_id` через
  явный параметр `predict_back_category_id`. После отмены FSM прогноза
  пользователь приземляется в категории события, а не обратно в «Мои
  прогнозы»: это сознательная MVP-компромисс, потому что CallbackData не
  вкладываются, а пробрасывать «back-target» через FSM-state требует расширения
  трёх callback'ов. Если в review решат, что это критично — добавим в TASK-015+.
- **Step 1.1 — `allow_archived`.** В `render_event_card` добавлен
  keyword-параметр `allow_archived: bool = False`. Из «Мои прогнозы → Архив»
  передаём True, чтобы карточка отображалась для архивных событий. `on_event`
  и `on_predict_cancel` оставлены без этого параметра — поведение «карточка
  недоступна» для архивных событий через каталог сохранено.
- **Step 2 — callback-data.** Добавлены `MyTab = Literal["active", "archive"]`,
  `MyTabCb(tab, page=0)` префикс `"m"`, `MyPredictionCb(event_id, tab)` префикс
  `"mp"`.
- **Step 3 — клавиатура.** `my_predictions_kbd(events, *, tab, page, has_prev,
  has_next)` собирает 1 кнопку на прогноз (текст = `event.title`) + ряд из двух
  табов (активный отмечен `✓`) + опц. ряд пагинации `‹/›`. «🏠 В меню» не
  добавлено — есть постоянный ReplyKeyboard главного меню.
- **Step 4 — router `src/bot/routers/my.py`.** `cmd_my` + `on_my_tab` +
  `on_my_prediction` + helper `_build_my_view(user, session, *, tab, page) →
  (text, kbd)`. `PAGE_SIZE = 7` (как в `events.py`). N+1 при подгрузке `event`
  для каждого прогноза — приемлемо на MVP (7 запросов на страницу).
- **Step 5 — тексты.** 7 новых констант: `MY_HEADER_ACTIVE`,
  `MY_HEADER_ARCHIVE`, `MY_NO_ACTIVE`, `MY_NO_ARCHIVE`, `MY_ROW_ACTIVE` (4
  поля), `MY_ROW_ARCHIVE` (5 полей, включая `status_emoji ∈ {✅, ❌, ⏳}`),
  `MY_STATS`.
- **Step 6 — тесты.** 10 новых mock-based unit-тестов в
  `tests/unit/bot/routers/test_my_handler.py`. Регресс существующих
  `test_events_handler.py` и `test_prediction_handler.py` не потребовался —
  они проверяют поведение через сервис-моки и `edit_text.assert_awaited_once`,
  не смотрят в детали клавиатуры. Все 105 unit-тестов зелёные после
  рефакторинга.

## Изменённые файлы

```
+ src/bot/routers/my.py                       # router cmd_my/on_my_tab/on_my_prediction
* src/bot/callbacks.py                        # +MyTab, MyTabCb, MyPredictionCb
* src/bot/keyboards/__init__.py               # +my_predictions_kbd, event_card_kbd новая сигнатура
* src/bot/routers/events.py                   # render_event_card: back_button + allow_archived
* src/bot/routers/prediction.py               # on_predict_cancel: собирает back_button
* src/bot/texts.py                            # +7 MY_* констант
+ tests/unit/bot/routers/test_my_handler.py   # 10 mock-based тестов
+ handoff/archive/TASK-014-my-predictions/task.md  # снапшот исходной задачи
+ handoff/outbox/TASK-014-report.md           # этот отчёт
```

## Как воспроизвести / запустить

```bash
# Линт
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Типы
uv run mypy src/shared/ src/bot/

# Тесты только новой задачи
uv run pytest tests/unit/bot/routers/test_my_handler.py -v

# Полный unit-набор
uv run pytest tests/unit/
```

## Что не сделано (компромиссы)

- **Back-target через FSM прогноза.** Если пользователь вошёл в predict-flow
  из «Мои прогнозы → событие → ✏️ Изменить прогноз», то после `❌ Отмена` или
  `✅ Подтвердить» он попадает не обратно в «Мои прогнозы», а в категорию
  события (через `PredictStartCb.back_category_id = event.category_id`).
  Причина: CallbackData не вкладываются друг в друга, и пробрасывание
  «back-target» через все три prediction-callback'ов требует расширения
  TASK-013. Для MVP смотрим, насколько это заметно в продакшен-использовании.
  Кандидат на cleanup-задачу TASK-014.1, если решат, что важно.
- **N+1 при рендере списка.** `_build_my_view` дёргает
  `EventService.get_event(event_id, with_outcomes=True)` на каждый прогноз
  в странице (до 7 запросов). Спецификация задачи это разрешает. Если в
  review увидим горячую точку — `PredictionRepository.list_*_by_user_with_relations`
  с одним SQL + `selectinload`.
- **Карточка события для архивных предсказаний.** Используется тот же
  `EVENT_CARD` шаблон, что и для активных — без «итог» и без «is_correct»
  бейджа. В `MY_ROW_ARCHIVE` эта инфа уже отображена, поэтому переход в
  карточку события не теряет данные, но и не показывает их повторно. Если
  в review решат, что нужна архивная карточка с итогом — отдельная задача.

## Открытые вопросы для проектировщика

1. **Back-через-FSM-прогноза.** Принимаем ли потерю back-target после
   «Изменить прогноз» из «Мои прогнозы»? Если нет — какой паттерн использовать
   (расширить prediction CB-классы новым полем `back_my_tab: MyTab | None`,
   или хранить back в FSM `state.update_data(back_button=...)` с
   сериализацией)?
2. **Текст кнопки прогноза в списке.** Сейчас просто `event.title`. Не
   добавляем эмодзи статуса (⏳ для активного, ✅/❌ для архива). Если хочется
   маркировать — могу добавить в Step 3 keyboard и обновить тесты.
3. **Маркер активного таба.** Сейчас `✓ 🟢 Активные` / `✓ 📦 Архив`. Альтернативы:
   убрать `✓` и менять только заголовок body. Текущий вариант явнее.
4. **`allow_archived` параметр в `render_event_card`.** Альтернативный дизайн —
   убрать guard на `is_archived` полностью (предсказательная логика и так
   проверяет `predictions_close_at`). Текущий вариант защищает «Все события» от
   гонки с админом, который архивировал событие пока пользователь просматривал
   список. Оставлять?
5. **Регресс existing-тестов.** Спека упоминала «регрессия `test_events_handler.py`
   + `test_prediction_handler.py` под новый `back_button`». Тесты прошли без
   изменений (они не инспектируют клавиатуру). Стоит ли добавить новые тесты,
   которые явно проверяют сборку `back_button` в `on_event` и `on_predict_cancel`?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — **TASK-014 закрыт:** раздел «📋 Мои прогнозы» в боте — `cmd_my`
  (Command + F.text) с дефолтной активной вкладкой, `on_my_tab` для переключения
  «🟢 Активные / 📦 Архив» и пагинации (`PAGE_SIZE=7`), `on_my_prediction` →
  `render_event_card` с кнопкой «🔙 К моим прогнозам». В архиве — `MY_STATS`
  через `StatsService.user_stats`. Рефакторинг: `render_event_card` /
  `event_card_kbd` приняли `back_button: tuple[str, CallbackData]` вместо
  `back_category_id`; `allow_archived` для входа из архива. Новые callback'и
  `MyTab`/`MyTabCb`/`MyPredictionCb`. 7 новых текстовых констант (`MY_*`).
  115 тестов (105 unit + 10 новых my_handler). PR #TBD → squash TBD;
  pre-task cleanup PR не понадобился (working tree чистый).
```

## Метрики

- Тестов добавлено: **10** (`test_my_handler.py`)
- Тестов всего: **105 unit** (включая существующие), все зелёные
- Файлов изменено: **6**, файлов создано: **1** (`my.py` уже существовал скелетом)
- Время выполнения: ~1ч
