---
id: TASK-013
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - docs/08-conventions.md
  - src/shared/services/prediction.py
  - src/shared/exceptions.py
  - src/bot/routers/events.py
priority: high
estimate: L
---

# TASK-013: FSM «Сделать прогноз» — выбор исхода, подтверждение, upsert

## Контекст

Третий реальный handler. После TASK-012 пользователь умеет дойти до карточки события (`/events` → категория → событие). Теперь нужен FSM-флоу: из карточки активного события пользователь жмёт «🎯 Сделать прогноз» (или «✏️ Изменить прогноз», если у него уже есть прогноз) → видит inline-список исходов → выбирает → видит подтверждение с напоминанием о дедлайне → подтверждает → запись через `PredictionService.make_prediction` (upsert: тот же метод и создаёт, и обновляет).

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) — раздел «Сделать прогноз»: FSM `MakingPrediction`, шаги «Выбор исхода» → «Подтверждение», edge cases (дедлайн прошёл, архивно, уже есть прогноз, событие архивно после фиксации итога).
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — `Prediction(user_id, event_id, outcome_id, is_correct, updated_at)`, уникальный `(user_id, event_id)`.
- [`src/shared/services/prediction.py`](../../src/shared/services/prediction.py) — `make_prediction(user_id, event_id, outcome_id)` уже умеет всё: проверки `EventNotPredictableError` (not_found / archived / not_published), `PredictionDeadlinePassedError`, `OutcomeNotForEventError`, upsert + commit. Дополнительной серверной логики в TASK-013 **не нужно**.
- [`src/shared/exceptions.py`](../../src/shared/exceptions.py) — доменные исключения, которые handler ловит и форматирует.
- [`src/bot/routers/events.py`](../../src/bot/routers/events.py) — паттерны handler'ов (auth-check, callback-data, `query.message.edit_text`). Карточка события (`on_event`) — точка входа в новый flow; туда же возврат «❌ Отмена».
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — строка 2026-05-23 про вынос `_check_access` в `@require_active_user`.

Открытые вопросы TASK-012, влияющие на эту задачу:

- **#3 (change):** `_check_access` inline → декоратор `@require_active_user`. Реализуем в Step 1 ниже. После этого 4 callback handler'а в `events.py` тоже переписываются на декоратор — это часть задачи.
- **#2 (keep):** `PAGE_SIZE` — TASK-013 не пагинирует, переноса нет.
- **#5 (keep):** datetime в UTC, формат `%d.%m %H:%M` для дедлайна в напоминалке подтверждения.

## Перед стартом — pre-task cleanup PR

Перед основной работой — стандартный pre-task cleanup PR ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку, в `origin/main` накопились правки cowork:

- [`CLAUDE.md`](../../CLAUDE.md) — новый раздел «Push обязателен после каждой задачи» + переписан раздел «Когда задача готова» (5 → 6 шагов, явный merge + `git pull`).
- [`handoff/README.md`](../README.md) — новый раздел «Зеркало в Google Drive» (`Claude projects/Betting Bot backup` зеркалирует handoff для второго локального CC).
- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-012, новые «Следующие шаги».
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 4 новых строки (TASK-012 решения).
- Новая сессия [`sessions/2026-05-23-11-task-012-review/`](../../sessions/2026-05-23-11-task-012-review/).

Упакуй в `chore/post-TASK-012-cowork-cleanup`, открой PR `chore(handoff): post-TASK-012 review by cowork`, замерджи. После — ветка `feature/TASK-013-prediction-flow` от свежего `main`.

## Цель

Пользователь из карточки активного события может сделать или изменить прогноз через двухшаговый FSM: выбрать исход → подтвердить. Запись идёт через готовый `PredictionService.make_prediction` (upsert). Все доменные исключения превращены в понятные тексты. Заодно — `_check_access` рефакторится в декоратор `@require_active_user`, который заменяет inline-helper во всех 4 handler'ах `events.py` и используется в 5 новых handler'ах `prediction.py`. Покрыто unit-тестами (mock-based, как в TASK-012).

## Definition of Done

### Step 1 — Декоратор `@require_active_user` (рефакторинг `_check_access`)

- [ ] **Новый файл `src/bot/auth.py`** с module docstring «Декоратор `@require_active_user` — проверка регистрации и блокировки пользователя на handler'ах бота».
- [ ] Реализация:
  ```python
  from collections.abc import Awaitable, Callable
  from functools import wraps
  from typing import Any, ParamSpec, TypeVar

  from aiogram.types import CallbackQuery, Message

  from src.shared.models import User

  from . import texts

  P = ParamSpec("P")
  R = TypeVar("R")


  def require_active_user(
      handler: Callable[..., Awaitable[Any]],
  ) -> Callable[..., Awaitable[Any]]:
      """Перед вызовом handler'а проверяет `user`: None → NEED_START, blocked → ACCESS_DENIED.

      Handler должен принимать первым позиционным аргументом `Message` или
      `CallbackQuery` и иметь в kwargs `user: User | None`. Декоратор сужает тип
      `user` до `User` для самого handler'а (он не должен снова проверять None).
      """

      @wraps(handler)
      async def wrapper(event: Message | CallbackQuery, *args: Any, **kwargs: Any) -> Any:
          user: User | None = kwargs.get("user")
          deny_text = _deny_text(user)
          if deny_text is not None:
              if isinstance(event, CallbackQuery):
                  await event.answer(deny_text, show_alert=True)
              else:
                  await event.answer(deny_text)
              return None
          return await handler(event, *args, **kwargs)

      return wrapper


  def _deny_text(user: User | None) -> str | None:
      if user is None:
          return texts.NEED_START
      if user.is_blocked:
          return texts.ACCESS_DENIED
      return None
  ```
- [ ] Сигнатура handler'а после декорирования может оставаться `user: User | None`, но handler внутри **не должен** снова проверять None/blocked. mypy с этим живёт (декоратор не сужает тип в сигнатуре, но логически — сужает).
- [ ] **Переписать `src/bot/routers/events.py`:** удалить `_check_access`, навесить `@require_active_user` на `cmd_events`, `on_back_to_categories`, `on_category`, `on_event`. Внутри handler'ов убрать `deny = _check_access(user); if deny is not None: ...` блоки. Все 4 handler'а должны стать короче.
- [ ] **Проверить, что существующие тесты в `tests/unit/bot/routers/test_events_handler.py` (особенно `test_cmd_events_unauthenticated_sends_need_start` и `test_cmd_events_blocked_sends_access_denied`) продолжают проходить.** При необходимости — обновить ожидания (декоратор отвечает тем же текстом, тест должен остаться валидным).
- [ ] **Новые тесты декоратора** в `tests/unit/bot/test_auth.py`:
  - `test_require_active_user_passes_through_for_active_user_message`
  - `test_require_active_user_passes_through_for_active_user_callback`
  - `test_require_active_user_returns_need_start_for_none_user_message`
  - `test_require_active_user_returns_need_start_for_none_user_callback` (с `show_alert=True`)
  - `test_require_active_user_returns_access_denied_for_blocked_user_message`
  - `test_require_active_user_returns_access_denied_for_blocked_user_callback` (с `show_alert=True`)

### Step 2 — FSM-state `MakingPrediction`

- [ ] **`src/bot/states.py`** — реализовать (сейчас заглушка):
  ```python
  """FSM-states aiogram. Регистрируется в RedisStorage."""

  from __future__ import annotations

  from aiogram.fsm.state import State, StatesGroup

  __all__ = ["MakingPrediction"]


  class MakingPrediction(StatesGroup):
      choosing_outcome = State()
      confirming = State()
  ```
- [ ] FSM-data в этом flow содержит:
  - `event_id: int` — обязательно, ставится при входе в `choosing_outcome`.
  - `back_category_id: int | None` — для возврата на карточку события при «❌ Отмена» (берётся из `EventCb.back_category_id` карточки). На MVP можно положить `None` и из FSM-data возвращать в главное меню.
- [ ] **Не хранить `outcome_id` в FSM-data** — он передаётся через callback `PredictPickCb(event_id, outcome_id)`, а потом через `PredictConfirmCb(event_id, outcome_id)`. Это спасает от рассинхрона state ↔ callback.

### Step 3 — Новые callback-data классы

- [ ] **В `src/bot/callbacks.py`** добавить (после существующих):
  ```python
  class PredictStartCb(CallbackData, prefix="p"):
      """Старт FSM прогноза из карточки события."""

      event_id: int
      back_category_id: int | None


  class PredictPickCb(CallbackData, prefix="po"):
      """Выбран исход — переход к шагу подтверждения."""

      event_id: int
      outcome_id: int


  class PredictConfirmCb(CallbackData, prefix="pc"):
      """Финальное подтверждение прогноза."""

      event_id: int
      outcome_id: int


  class PredictCancelCb(CallbackData, prefix="px"):
      """Отмена прогноза — возврат на карточку события."""

      event_id: int
      back_category_id: int | None
  ```
- [ ] Обнови `__all__`. Префиксы короткие (1-2 буквы) — лимит 64 байта на `callback_data`.

### Step 4 — Расширение `event_card_kbd` (показ кнопки прогноза)

- [ ] **В `src/bot/keyboards/__init__.py`** изменить сигнатуру `event_card_kbd`:
  ```python
  def event_card_kbd(
      *,
      event_id: int,
      back_category_id: int | None,
      can_predict: bool,
      has_prediction: bool,
  ) -> InlineKeyboardMarkup:
  ```
  - Если `can_predict` — первой кнопкой:
    - «✏️ Изменить прогноз» (callback `PredictStartCb(event_id, back_category_id)`) если `has_prediction`,
    - «🎯 Сделать прогноз» (callback `PredictStartCb(event_id, back_category_id)`) если нет.
  - Если `can_predict=False` — кнопка прогноза не показывается (по спеке: «Кнопка `🎯 Сделать прогноз` не показывается. Если пользователь жмёт кнопку из старого сообщения — бот отвечает "Приём прогнозов завершён"» — последнее покрывается серверной проверкой в handler'е, см. Step 6).
  - Затем «🔙 К событиям» — как сейчас.
  - `builder.adjust(1)` — по одной кнопке в ряд.
- [ ] **В `on_event` (`src/bot/routers/events.py`):** сейчас `event_card_kbd(back_category_id=...)` вызывается без новых параметров. Нужно посчитать:
  - `can_predict = not event.is_archived and event.is_published and event.predictions_close_at > datetime.now(tz=UTC)`. Возьми `datetime.now(tz=UTC)`, не `datetime.utcnow()` (правило `docs/08-conventions.md`).
  - `has_prediction = existing is not None` (переменная `existing` уже есть).
  - Передай оба в `event_card_kbd(event_id=event.id, back_category_id=..., can_predict=..., has_prediction=...)`.

### Step 5 — Новые клавиатуры прогноза

- [ ] **`predict_outcomes_kbd(event_id, outcomes, back_category_id)` → `InlineKeyboardMarkup`:**
  - По одной кнопке на исход: `text=f"{i + 1}) {outcome.label}"`, callback `PredictPickCb(event_id, outcome.id)`.
  - Последняя кнопка — «❌ Отмена», callback `PredictCancelCb(event_id, back_category_id)`.
  - `builder.adjust(1)`.
- [ ] **`predict_confirm_kbd(event_id, outcome_id, back_category_id)` → `InlineKeyboardMarkup`:**
  - «✅ Подтвердить» — `PredictConfirmCb(event_id, outcome_id)`.
  - «🔙 Назад» — `PredictPickCb(event_id, outcome_id=-1)` НЕ ГОДИТСЯ; нужно вернуться в `choosing_outcome` с показом списка исходов. Используй отдельный callback или возвращайся через `PredictStartCb(event_id, back_category_id)` (он повторно ставит state в `choosing_outcome` и рендерит список). Я предпочитаю **второй вариант** — `PredictStartCb` идемпотентен.
  - `builder.adjust(2)` — две кнопки в ряд.
- [ ] Обнови `__all__`.

### Step 6 — Handler в `src/bot/routers/prediction.py`

- [ ] **Module docstring** «Router /predict и FSM `MakingPrediction` (TASK-013)».
- [ ] Импорты: `Command`, `F`, `Router`, `CallbackQuery`, `Message`, `FSMContext`, `AsyncSession`, `User`, доменные исключения, `PredictionService`, `EventService`, `keyboards`, `texts`, callbacks, `MakingPrediction`, `require_active_user`.
- [ ] `router = Router(name="prediction")`.
- [ ] **Entry-point из главного меню** — `cmd_predict`:
  ```python
  @router.message(Command("predict"))
  @router.message(F.text == "🎯 Сделать прогноз")
  @require_active_user
  async def cmd_predict(
      message: Message,
      user: User | None,
      session: AsyncSession,
      state: FSMContext,
  ) -> None:
      """Из главного меню — перенаправление в каталог. Карточка события → FSM."""
      await state.clear()
      # Переиспользуем cmd_events: тот же каталог категорий → события → карточка.
      from .events import cmd_events  # локальный импорт, чтобы избежать круговой зависимости
      await cmd_events(message, user=user, session=session)
  ```
  - Это даёт один extra-клик по сравнению со спекой (`docs/04-bot-flows.md`: «при выборе события → шаг выбора исхода»). Решение принято в review TASK-012: прямой entry-point — отдельной TASK-013a, если UX покажет, что мешает.
  - Локальный импорт `from .events import cmd_events` — единственный способ избежать круга (оба router'а пакуются в `all_routers` через `routers/__init__.py`).
- [ ] **`on_predict_start`** — открытие FSM из карточки события:
  ```python
  @router.callback_query(PredictStartCb.filter())
  @require_active_user
  async def on_predict_start(
      query: CallbackQuery,
      callback_data: PredictStartCb,
      user: User | None,
      session: AsyncSession,
      state: FSMContext,
  ) -> None:
  ```
  - `event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)`.
  - Если `event is None` или `event.is_archived` или not `event.is_published` → `await query.answer(texts.EVENT_NOT_AVAILABLE, show_alert=True)`; `await state.clear()`; return.
  - Если `event.predictions_close_at <= datetime.now(tz=UTC)` → `await query.answer(texts.PREDICT_DEADLINE_PASSED, show_alert=True)`; `await state.clear()`; return.
  - `await state.set_state(MakingPrediction.choosing_outcome)`.
  - `await state.update_data(event_id=event.id, back_category_id=callback_data.back_category_id)`.
  - `text = texts.PREDICT_PICK_OUTCOME.format(title=event.title)`.
  - `await query.message.edit_text(text, reply_markup=keyboards.predict_outcomes_kbd(event.id, event.outcomes, callback_data.back_category_id))`.
  - `await query.answer()`.
- [ ] **`on_predict_pick`** — выбран исход, показ подтверждения:
  ```python
  @router.callback_query(PredictPickCb.filter(), MakingPrediction.choosing_outcome)
  @require_active_user
  async def on_predict_pick(
      query: CallbackQuery,
      callback_data: PredictPickCb,
      user: User | None,
      session: AsyncSession,
      state: FSMContext,
  ) -> None:
  ```
  - `event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)`.
  - Те же проверки event-доступности и дедлайна — между шагами могла пройти архивация / истечь дедлайн.
  - Если исход не принадлежит событию: `outcome = next((o for o in event.outcomes if o.id == callback_data.outcome_id), None)`; если None → `query.answer(texts.PREDICT_OUTCOME_NOT_FOUND, show_alert=True)`; `state.clear()`; return.
  - `await state.set_state(MakingPrediction.confirming)`.
  - `text = texts.PREDICT_CONFIRM.format(label=outcome.label, close_at_fmt=event.predictions_close_at.strftime("%d.%m %H:%M"))`.
  - `back_category_id = (await state.get_data()).get("back_category_id")`.
  - `await query.message.edit_text(text, reply_markup=keyboards.predict_confirm_kbd(event.id, outcome.id, back_category_id))`.
  - `await query.answer()`.
- [ ] **`on_predict_confirm`** — финальное подтверждение:
  ```python
  @router.callback_query(PredictConfirmCb.filter(), MakingPrediction.confirming)
  @require_active_user
  async def on_predict_confirm(
      query: CallbackQuery,
      callback_data: PredictConfirmCb,
      user: User | None,
      session: AsyncSession,
      state: FSMContext,
  ) -> None:
  ```
  - `service = PredictionService(session)`.
  - Запомнить, было ли это «новый» или «обновление» — для текста: `existing = await service.get_user_prediction(user.id, callback_data.event_id)`; `was_new = existing is None`.
  - Внутри `try:`:
    - `prediction = await service.make_prediction(user_id=user.id, event_id=callback_data.event_id, outcome_id=callback_data.outcome_id)`.
    - `event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)`; `outcome = next(o for o in event.outcomes if o.id == prediction.outcome_id)` (он гарантированно есть после успешного `make_prediction`).
    - `text = (texts.PREDICT_SAVED if was_new else texts.PREDICT_UPDATED).format(label=outcome.label)`.
    - `await query.message.edit_text(text)` (без клавиатуры — пользователь увидит ReplyKeyboard главного меню от старых сообщений).
    - `logger.info("bot.predict.saved", user_id=user.id, event_id=event.id, outcome_id=outcome.id, was_new=was_new)`.
  - `except EventNotPredictableError as exc:` → `query.answer(texts.PREDICT_EVENT_UNAVAILABLE, show_alert=True)`; logger.info с `reason=exc.reason`.
  - `except PredictionDeadlinePassedError:` → `query.answer(texts.PREDICT_DEADLINE_PASSED, show_alert=True)`.
  - `except OutcomeNotForEventError:` → `query.answer(texts.PREDICT_OUTCOME_NOT_FOUND, show_alert=True)`.
  - `finally: await state.clear()` — FSM сбрасывается в любом случае (успех или ошибка).
  - `await query.answer()` в успешной ветке (после `edit_text`).
- [ ] **`on_predict_cancel`** — отмена → возврат на карточку события:
  ```python
  @router.callback_query(PredictCancelCb.filter())
  @require_active_user
  async def on_predict_cancel(
      query: CallbackQuery,
      callback_data: PredictCancelCb,
      user: User | None,
      session: AsyncSession,
      state: FSMContext,
  ) -> None:
  ```
  - `await state.clear()`.
  - Вернуться на карточку события: реиспользовать `on_event` из `events.py` нельзя (там сигнатура с `EventCb`). Самое простое — продублировать рендер карточки или вынести его в shared helper `render_event_card` в `src/bot/routers/events.py` и вызвать его отсюда. **Делай через вынос в helper** — это и для TASK-014 пригодится.
  - Helper: `async def render_event_card(query: CallbackQuery, event_id: int, back_category_id: int | None, user: User, session: AsyncSession) -> None` — собирает текст и клавиатуру, делает `query.message.edit_text(...)` и `query.answer()`. `on_event` в `events.py` тоже переписывается на этот helper.
  - `on_predict_cancel` вызывает `render_event_card(query, callback_data.event_id, callback_data.back_category_id, user, session)`.

### Step 7 — Тексты

- [ ] **В `src/bot/texts.py`** добавить (с обновлением `__all__`):
  - `PREDICT_PICK_OUTCOME = "🎯 Сделайте прогноз: «{title}»\n\nВыберите один из вариантов:"`
  - `PREDICT_CONFIRM = "Вы выбрали: «{label}»\n\n⚠️ Изменить прогноз можно до {close_at_fmt}."`
  - `PREDICT_SAVED = "✅ Прогноз сохранён: «{label}»"`
  - `PREDICT_UPDATED = "✏️ Прогноз обновлён: «{label}»"`
  - `PREDICT_DEADLINE_PASSED = "Приём прогнозов по этому событию завершён."`
  - `PREDICT_EVENT_UNAVAILABLE = "Событие больше недоступно для прогнозов."`
  - `PREDICT_OUTCOME_NOT_FOUND = "Выбранный исход больше недоступен. Откройте событие заново."`
  - Кнопочные тексты (`🎯 Сделать прогноз`, `✏️ Изменить прогноз`, `✅ Подтвердить`, `🔙 Назад`, `❌ Отмена`) — оставь хардкодом внутри `keyboards/__init__.py`, не выноси в texts. Граница: тексты сообщений — в `texts.py`, тексты кнопок inline-клавиатур — в keyboards (TASK-012 уже использует этот стиль с «🔙 К событиям»).
- [ ] **`description_block` / `prediction_block`** в карточке события не трогаются — оставлены как в TASK-012.

### Step 8 — Unit-тесты handler'ов

`tests/unit/bot/routers/test_prediction_handler.py` — mock-based, как в TASK-012:

- [ ] **`on_predict_start`:**
  - `test_predict_start_unauthenticated_returns_alert` (декоратор)
  - `test_predict_start_blocked_returns_alert` (декоратор)
  - `test_predict_start_event_not_found_clears_state_and_alerts`
  - `test_predict_start_event_archived_alerts`
  - `test_predict_start_event_not_published_alerts`
  - `test_predict_start_deadline_passed_alerts`
  - `test_predict_start_active_event_sets_state_and_shows_outcomes`
- [ ] **`on_predict_pick`:**
  - `test_predict_pick_unknown_outcome_clears_state_and_alerts`
  - `test_predict_pick_valid_outcome_sets_confirming_state`
- [ ] **`on_predict_confirm`:**
  - `test_predict_confirm_new_prediction_calls_make_prediction_and_shows_saved`
  - `test_predict_confirm_existing_prediction_shows_updated`
  - `test_predict_confirm_deadline_passed_shows_alert_and_clears_state`
  - `test_predict_confirm_outcome_not_for_event_shows_alert`
  - `test_predict_confirm_event_not_predictable_shows_alert`
- [ ] **`on_predict_cancel`:**
  - `test_predict_cancel_clears_state_and_returns_to_event_card`
- [ ] **`cmd_predict`:**
  - `test_cmd_predict_delegates_to_cmd_events`
  - Достаточно проверить, что после вызова `cmd_predict` `message.answer` был вызван с `texts.CATEGORIES_PROMPT` (либо `texts.NO_EVENTS_AT_ALL`).

Pattern для FSM-моков:

```python
def _mock_state() -> MagicMock:
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={"back_category_id": None})
    return state
```

`PredictionService` / `EventService` патчатся через `monkeypatch.setattr("src.bot.routers.prediction.PredictionService", factory)` — тот же стиль, что в `test_events_handler.py`.

### Step 9 — Unit-тесты декоратора

`tests/unit/bot/test_auth.py`:

- [ ] 6 тестов из Step 1 чек-листа.
- [ ] Декоратор покрывается изолированно, на dummy handler-функции `async def _dummy(event, user): return "OK"`.

### Step 10 — Регрессия по существующим тестам

- [ ] `tests/unit/bot/routers/test_events_handler.py` — после переписывания `events.py` на декоратор, все 13 существующих тестов должны продолжать проходить. Если падают — фикси тесты (не handler) на ту же ожидаемую логику.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный. Декоратор `@require_active_user` может потребовать `# type: ignore[misc]` на handler'ах, если mypy ругнётся на параметры — это допустимо (комментарием «декоратор не сужает тип в сигнатуре, но логически — сужает»).
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit-тесты (включая ~20 новых).
- [ ] `uv run pytest tests/integration -m integration` — без падений (новых integration-тестов в TASK-013 нет — `PredictionService` уже покрыт в TASK-009).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):** `make up && make migrate`, создать тестовое событие с 2-3 исходами, запустить бота `uv run python -m src.bot.main`, в Telegram пройти: `/events` → категория → событие → «🎯 Сделать прогноз» → исход → «✅ Подтвердить». Затем повторно: «✏️ Изменить прогноз» → другой исход → подтвердить. Проверить отмену.
- [ ] Ветка `feature/TASK-013-prediction-flow`, Conventional Commits:
  - `feat(bot): @require_active_user decorator (refactor _check_access)`
  - `feat(bot): MakingPrediction FSM states`
  - `feat(bot): prediction callback data + keyboards`
  - `feat(bot): prediction router — FSM choose/confirm/cancel`
  - `feat(bot): event card shows "Сделать прогноз" when can_predict`
  - `feat(texts): prediction ui constants`
  - `test(bot): require_active_user decorator tests`
  - `test(bot): prediction router tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-013-report.md`, задача → `handoff/archive/TASK-013-prediction-flow/task.md`.

## Артефакты

```
+ src/bot/auth.py                                         # @require_active_user
* src/bot/states.py                                       # MakingPrediction
* src/bot/callbacks.py                                    # +4 callback classes
* src/bot/keyboards/__init__.py                           # +2 фабрики, изменён event_card_kbd
* src/bot/texts.py                                        # +7 констант
* src/bot/routers/events.py                               # рефакторинг на декоратор, render_event_card helper
* src/bot/routers/prediction.py                           # cmd_predict + 4 callback handler'а
* tests/unit/bot/routers/test_events_handler.py           # обновлены под рефакторинг
+ tests/unit/bot/routers/test_prediction_handler.py       # ~15 тестов
+ tests/unit/bot/test_auth.py                             # 6 тестов
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Сделать прогноз»
- [docs/03-data-model.md](../../docs/03-data-model.md) — `Prediction`
- [src/shared/services/prediction.py](../../src/shared/services/prediction.py) — готовый сервис
- [src/shared/exceptions.py](../../src/shared/exceptions.py) — доменные исключения
- [src/bot/routers/events.py](../../src/bot/routers/events.py) — образец паттернов handler'ов
- [src/bot/routers/start.py](../../src/bot/routers/start.py) — образец FSM `state.clear()` + структура ветвления
- [tests/unit/bot/routers/test_events_handler.py](../../tests/unit/bot/routers/test_events_handler.py) — образец mock-тестов
- [state/DECISIONS.md](../../state/DECISIONS.md) — строки про вынос `_check_access`, UTC-форматирование, `PAGE_SIZE`
- [handoff/outbox/TASK-012-report.md](../outbox/TASK-012-report.md)

## Подсказки исполнителю

- **`PredictionService.make_prediction` — единственная точка записи.** Метод уже делает `upsert` (тот же call и для «создать», и для «изменить»). Не дублируй его проверки в handler'е — лови исключения и форматируй текст. Различие «новый / обновлён» определяется до вызова через `get_user_prediction(user_id, event_id)` — нужно только для текста ответа.
- **`@require_active_user` + aiogram-фильтры.** Декоратор стоит **после** `@router.callback_query(...)` (внешний декоратор оборачивает внутренний). aiogram передаёт `callback_data`, `state`, `user`, `session` через kwargs — декоратор пробрасывает их в `**kwargs` без трогания.
- **FSM-фильтры в `@router.callback_query(...)`:** `@router.callback_query(PredictPickCb.filter(), MakingPrediction.choosing_outcome)` — оба фильтра комбинируются по AND. Если state неподходящий (например, пользователь жмёт кнопку из старого сообщения) — handler не вызывается; aiogram оставит callback без ответа, и у пользователя крутятся «часики» 30 секунд. Чтобы этого избежать — повесь fallback-handler без state-фильтра:
  ```python
  @router.callback_query(PredictPickCb.filter())
  async def on_predict_pick_no_state(query: CallbackQuery) -> None:
      await query.answer(texts.PREDICT_EVENT_UNAVAILABLE, show_alert=True)
  ```
  Регистрируй его **после** stateful-версии — aiogram проверяет handler'ы по порядку.
- **Локальный импорт `from .events import cmd_events`** в `prediction.py` нужен только для `cmd_predict` — основная зависимость одна. Не выноси оба router'а в общий модуль, не делай `bot/dispatcher.py` — это излишнее.
- **`render_event_card` helper** — выноси в `src/bot/routers/events.py` (не в keyboards и не в новый файл). Это часть events-flow, prediction router его лишь использует. Сигнатура: `async def render_event_card(query: CallbackQuery, event_id: int, back_category_id: int | None, user: User, session: AsyncSession) -> None`. Возвращает None, сам делает `query.message.edit_text(...)` + `query.answer()`. Имя в `__all__` экспортируется.
- **`OutcomeNotForEventError` vs «исход не найден в `event.outcomes`»:** в `on_predict_pick` — отбрасываем сразу (быстрый возврат), не идём в сервис. В `on_predict_confirm` — может случиться при гонке (админ удалил исход между шагами); сервис поднимет исключение, ловим.
- **`@wraps(handler)` в декораторе обязателен** — иначе aiogram не увидит сигнатуру handler'а через интроспекцию (`inspect.signature(...)`), и dependency injection (`session`, `user`, `state`, `callback_data`) сломается.
- **mypy на декораторе:** `Callable[..., Awaitable[Any]]` — самый безопасный тип. Точнее затипизировать через `ParamSpec` сложно из-за того, что декоратор хочет видеть `Message | CallbackQuery` первым аргументом, а handler'ы могут принимать его как `message: Message` или `query: CallbackQuery` — два разных типа в одной сигнатуре через `ParamSpec` не вырастают. `Any` тут оправдан, в `src/bot/` mypy не strict (`docs/08-conventions.md`).
- **Состояние FSM на отмену и ошибки — обязательно clear.** `await state.clear()` в `finally` ветки confirm и в начале cancel. Иначе после ошибки пользователь застрянет в FSM, и следующий `/start` его освободит (там уже есть `state.clear()`), но это плохой UX.
- **`logger.info("bot.predict.saved", ...)`** — структурное событие. Поля: `user_id`, `event_id`, `outcome_id`, `was_new` (bool). Не логируй сам `outcome.label` — это деталь презентации, не доменный факт. По правилам `docs/08-conventions.md` логи — структурные, не f-строки.
- **`query.message` может быть `InaccessibleMessage` в новых aiogram-апдейтах.** Делай `isinstance(query.message, Message)` перед `edit_text` (паттерн уже есть в `events.py`). Если не Message — `query.answer(text, show_alert=True)` как fallback.

## Что НЕ делать

- Не создавать новые методы в `PredictionService` или `EventService` — все нужные уже есть.
- Не добавлять прямой entry-point из главного меню «🎯 Сделать прогноз» с пропуском карточки события (новые `EventForPredictCb` и параллельные клавиатуры) — это отдельная TASK-013a, если понадобится.
- Не выносить `PAGE_SIZE` в `src/bot/_consts.py` — TASK-013 пагинации не использует.
- Не делать integration-тесты bot-handler'ов с реальной aiogram-сетью — mock-based unit-тестов достаточно.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` (за пределами стандартного pre-task cleanup PR со свежими правками cowork).
- Не добавлять новые зависимости.
- Не менять `PredictionService.make_prediction` (он уже делает upsert и нужные проверки).
- Не подменять `RedisStorage` на in-memory storage в тестах — все FSM-тесты handler'ов идут через mock `FSMContext`.
