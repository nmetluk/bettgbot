---
id: TASK-015
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - docs/08-conventions.md
  - src/shared/services/reminder.py
  - src/shared/models/reminder_setting.py
  - src/shared/exceptions.py
priority: high
estimate: L
---

# TASK-015: настройка напоминаний — глобальный toggle + интервалы + FSM

## Контекст

Пятый реальный handler. Пользователь открывает «🔔 Напоминания» (или `/reminders`) и видит свой текущий статус: включены ли напоминания глобально и какие интервалы активны (по умолчанию `[1440, 60]` — за сутки и за час, задано в `UserService.register_or_authenticate` при первой регистрации, см. TASK-011). Через FSM `EditingReminders` пользователь может: включить/выключить глобально, добавить интервал (пресет из 6 кнопок или свой ввод), удалить интервал.

Серверная логика **полностью готова**:

- [`src/shared/services/reminder.py`](../../src/shared/services/reminder.py): `ReminderService.get(user_id) → ReminderSetting | None`, `ReminderService.update(*, user_id, enabled, offsets_minutes)` — валидирует лимит ≤5, минимум 5 минут, дубли через `InvalidReminderOffsetsError`. Сохраняет в БД, коммитит.
- [`src/shared/models/reminder_setting.py`](../../src/shared/models/reminder_setting.py): модель `ReminderSetting(user_id, enabled, offsets_minutes: list[int], updated_at)`.
- [`src/shared/exceptions.py`](../../src/shared/exceptions.py): `InvalidReminderOffsetsError`.

Спецификация UX/UI — [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md), раздел «Настройка напоминаний» (меню, пресеты, парсер свободного ввода, edge cases).

## Перед стартом — pre-task cleanup PR (ОБЯЗАТЕЛЬНО)

В origin/main `e3fbbd4` → ... → `5097491` — последний коммит archive TASK-014. **Working tree этой машины (где cowork писал review-артефакты) содержит правки, которых нет в origin**:

- `state/PROJECT_STATUS.md` — закрытие TASK-013 + Drive-зеркало + закрытие TASK-014 + новые «Следующие шаги».
- `state/DECISIONS.md` — 10 новых строк за две сессии review (TASK-013 + TASK-014).
- `state/BACKLOG.md` — 2 новых пункта тех-долга (back-target FSM, N+1 в `_build_my_view`).
- `handoff/README.md` — новая секция «Зеркало в Google Drive» (переписанная под MCP-коннектор).
- Новые сессии: `sessions/2026-05-23-12-task-013-review/`, `sessions/2026-05-23-13-task-014-review/`.
- **Лишний файл:** `handoff/inbox/TASK-014-my-predictions.md` — он уже в `handoff/archive/TASK-014-my-predictions/task.md`, дубликат остался потому, что задача выполнялась на **другой машине** через Drive backup, а не из локального inbox. Удалить через `git rm` (или просто `rm` + `git add -A`).

Упакуй в `chore/post-TASK-014-cowork-cleanup`, открой PR `chore(handoff): post-TASK-013 + TASK-014 review by cowork`, замерджи. После — ветка `feature/TASK-015-reminders` от свежего `main`.

## Цель

Пользователь видит и меняет свои настройки напоминаний через двух/трёх-шаговый FSM. Покрыто mock-based unit-тестами. Парсер свободного ввода защищён от мусора (понимает форматы `15m` / `1h` / `2d` / число минут, отвергает остальное). Валидация лимитов и дубликатов через `ReminderService.update` — handler ловит `InvalidReminderOffsetsError` и показывает понятный текст.

## Definition of Done

### Step 1 — FSM `EditingReminders`

- [ ] **В `src/bot/states.py`** добавить:
  ```python
  class EditingReminders(StatesGroup):
      """FSM настройки напоминаний.

      - `adding_offset` — пользователь нажал «➕ Добавить» и видит пресеты или
        ждёт текстового ввода.
      """

      adding_offset = State()
  ```
- [ ] **Удаление интервала** делается **без FSM** — через `RemoveOffsetCb(offset)` подтверждать-не-подтверждать не нужно (одно нажатие = удалить); рендер меню обновляется. Это упрощает поток.
- [ ] **Toggle глобального enabled** — тоже без FSM, через `ToggleRemindersCb()` callback.
- [ ] **Свой ввод offset'а** — пользователь в состоянии `adding_offset` шлёт текстовое сообщение (`Message(F.text)`), парсер разбирает.

### Step 2 — Новые callback-data классы

- [ ] **В `src/bot/callbacks.py`** добавить (после существующих):
  ```python
  class RemindersMenuCb(CallbackData, prefix="r"):
      """Возврат в главное меню напоминаний (рендер заново)."""


  class ToggleRemindersCb(CallbackData, prefix="rt"):
      """Глобальный toggle enabled/disabled."""


  class AddOffsetCb(CallbackData, prefix="ra"):
      """Открыть подменю с пресетами + кнопкой ✍️ свой ввод."""


  class PresetOffsetCb(CallbackData, prefix="rp"):
      """Выбран пресет, минуты внутри callback."""

      minutes: int


  class CustomOffsetCb(CallbackData, prefix="rc"):
      """Запросить у пользователя текстовый ввод (state → adding_offset)."""


  class RemoveOffsetCb(CallbackData, prefix="rd"):
      """Удалить конкретный интервал."""

      minutes: int
  ```
  - Префиксы короткие (`r`, `rt`, `ra`, `rp`, `rc`, `rd`). Лимит callback_data — 64 байта.
- [ ] Обнови `__all__`.

### Step 3 — Клавиатуры

- [ ] **`reminders_menu_kbd(setting: ReminderSetting) → InlineKeyboardMarkup`** — основное меню:
  - Первой кнопкой — toggle: «🔕 Выключить» если `setting.enabled` иначе «🔔 Включить» (callback `ToggleRemindersCb()`).
  - Если `setting.enabled` И `setting.offsets_minutes`: рядом «➕ Добавить интервал» (callback `AddOffsetCb()`), затем по одной кнопке на каждый интервал в формате «🗑 {humanize(minutes)}» (callback `RemoveOffsetCb(minutes=minute)`). Сортировать по убыванию минут (как делает `ReminderService.update`).
  - Если `setting.enabled` И `not setting.offsets_minutes`: только «➕ Добавить интервал» (без списка для удаления).
  - Если `not setting.enabled`: только toggle (добавлять интервалы при выключенных глобально — можно, но в этой задаче упрощаем: при выключенных скрываем add/remove, чтобы UI был чище. Решение зафиксировано здесь).
  - `builder.adjust(1)` — по одной кнопке в ряд.
- [ ] **`reminders_add_kbd() → InlineKeyboardMarkup`** — подменю «Добавить интервал»:
  - 6 кнопок-пресетов: «15 минут» (callback `PresetOffsetCb(minutes=15)`), «30 минут» (30), «1 час» (60), «3 часа» (180), «12 часов» (720), «1 день» (1440).
  - Затем «✍️ Свой ввод» (callback `CustomOffsetCb()`).
  - Затем «🔙 Назад» (callback `RemindersMenuCb()`).
  - `builder.adjust(3, 3, 2)` — 6 пресетов в 2 ряда по 3 + ряд «свой ввод» + «🔙».
- [ ] **Helper `humanize_minutes(minutes: int) → str`** в `src/bot/keyboards/__init__.py`:
  - `< 60` → `"{N} мин"`
  - `< 1440` И `60 / N == 0` → `"{N} ч"` (например, 60 → «1 ч», 180 → «3 ч»)
  - `>= 1440` И `1440 / N == 0` → `"{N} д"`
  - Иначе → `"{H} ч {M} мин"` (например 90 → «1 ч 30 мин»).
  - Используется и в `reminders_menu_kbd` (для кнопок удаления), и в тексте меню (для строки «Сейчас вы получаете за: …»).
- [ ] Обнови `__all__`.

### Step 4 — Парсер свободного ввода

- [ ] **В `src/bot/routers/reminders.py`** (или в отдельном `src/bot/_reminders_parser.py`, если хочется тестировать изолированно — оптимально):
  ```python
  import re

  _OFFSET_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd]?)\s*$", re.IGNORECASE)


  def parse_offset(raw: str) -> int | None:
      """Возвращает offset в минутах или None, если ввод невалиден.

      Поддерживаемые форматы:
        - `15` → 15 минут (без суффикса = минуты)
        - `15m` → 15 минут
        - `1h` → 60 минут
        - `2d` → 2880 минут
      Граница диапазона: 5 ≤ result ≤ 10080 (неделя). Иначе None.
      """
      match = _OFFSET_PATTERN.match(raw)
      if not match:
          return None
      try:
          value = int(match.group(1))
      except ValueError:
          return None
      unit = match.group(2).lower()
      if unit == "h":
          value *= 60
      elif unit == "d":
          value *= 1440
      # без суффикса или "m" — минуты
      if value < 5 or value > 10080:
          return None
      return value
  ```
  - Минимум 5 минут — соответствует `ReminderService._MIN_OFFSET_MINUTES`.
  - Максимум 1 неделя (10080 минут) — разумный потолок; больший offset не имеет смысла (события обычно ближе чем неделя).
- [ ] **Покрыть `parse_offset` unit-тестами** отдельно (3-5 тестов: валидные, невалидные, граничные).

### Step 5 — Handler в `src/bot/routers/reminders.py`

- [ ] **Module docstring** «Router `/reminders` — настройка напоминаний (TASK-015)».
- [ ] Импорты: aiogram (`Command`, `F`, `Router`, `CallbackQuery`, `Message`, `FSMContext`), SQLAlchemy `AsyncSession`, `User`, `ReminderService`, `InvalidReminderOffsetsError`, keyboards, texts, callbacks (все новые `r*Cb`), `EditingReminders`, `require_active_user`.
- [ ] `router = Router(name="reminders")`.
- [ ] **`cmd_reminders`** — entry-point:
  ```python
  @router.message(Command("reminders"))
  @router.message(F.text == "🔔 Напоминания")
  @require_active_user
  async def cmd_reminders(
      message: Message, user: User | None, session: AsyncSession, state: FSMContext,
  ) -> None:
      assert user is not None
      await state.clear()  # на всякий случай — мог зайти из adding_offset
      service = ReminderService(session)
      setting = await service.get(user.id)
      # setting не None — гарантирует UserService.register_or_authenticate (TASK-011)
      assert setting is not None
      text = _format_menu_text(setting)
      await message.answer(text, reply_markup=keyboards.reminders_menu_kbd(setting))
  ```
- [ ] **`on_reminders_menu`** (`RemindersMenuCb`) — рендер заново через `query.message.edit_text(...)`. Используется при кнопке «🔙 Назад» из подменю.
- [ ] **`on_toggle_reminders`** (`ToggleRemindersCb`) — инвертирует `enabled`, сохраняет, перерендеривает меню:
  ```python
  setting = await service.get(user.id)
  await service.update(user_id=user.id, enabled=not setting.enabled, offsets_minutes=setting.offsets_minutes)
  setting = await service.get(user.id)  # перечитать
  await query.message.edit_text(_format_menu_text(setting), reply_markup=keyboards.reminders_menu_kbd(setting))
  await query.answer()
  ```
- [ ] **`on_add_offset`** (`AddOffsetCb`) — показать подменю пресетов:
  ```python
  await query.message.edit_text(
      texts.REMINDERS_ADD_PROMPT,
      reply_markup=keyboards.reminders_add_kbd(),
  )
  await query.answer()
  ```
- [ ] **`on_preset_offset`** (`PresetOffsetCb`) — добавить пресет, перерендерить меню:
  ```python
  setting = await service.get(user.id)
  new_offsets = list({*setting.offsets_minutes, callback_data.minutes})
  try:
      await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
  except InvalidReminderOffsetsError as exc:
      await query.answer(_format_error(exc), show_alert=True)
      return
  setting = await service.get(user.id)
  await query.message.edit_text(_format_menu_text(setting), reply_markup=keyboards.reminders_menu_kbd(setting))
  await query.answer()
  ```
  - `_format_error(exc)` распознаёт текст исключения (`"too many offsets"`, `"duplicate offsets"`, `"below minimum"`) и подбирает текст из `texts.REMINDERS_ERR_*`. Я бы предпочёл вернуть `exc.reason: Literal` из сервиса, но это требует правок сервиса (вне scope TASK-015). На MVP — match по строке исключения; вынесем доменный код причины в TASK-015-review при необходимости.
- [ ] **`on_custom_offset`** (`CustomOffsetCb`) — запросить текстовый ввод, перейти в state:
  ```python
  await state.set_state(EditingReminders.adding_offset)
  await query.message.edit_text(texts.REMINDERS_ASK_CUSTOM)  # без клавиатуры — пользователь шлёт текст
  await query.answer()
  ```
- [ ] **`on_custom_offset_input`** (`Message(F.text), EditingReminders.adding_offset`) — обработать текст:
  ```python
  @router.message(EditingReminders.adding_offset, F.text)
  @require_active_user
  async def on_custom_offset_input(
      message: Message, user: User | None, session: AsyncSession, state: FSMContext,
  ) -> None:
      assert user is not None
      assert message.text is not None
      minutes = parse_offset(message.text)
      if minutes is None:
          await message.answer(texts.REMINDERS_INVALID_INPUT)
          return  # state остаётся, пользователь может попробовать ещё раз
      service = ReminderService(session)
      setting = await service.get(user.id)
      assert setting is not None
      new_offsets = list({*setting.offsets_minutes, minutes})
      try:
          await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
      except InvalidReminderOffsetsError as exc:
          await message.answer(_format_error(exc))
          # не сбрасываем state — пусть попробует другой
          return
      await state.clear()
      setting = await service.get(user.id)
      await message.answer(
          texts.REMINDERS_ADDED.format(humanized=keyboards.humanize_minutes(minutes)),
          reply_markup=keyboards.reminders_menu_kbd(setting),
      )
  ```
- [ ] **`on_remove_offset`** (`RemoveOffsetCb`) — удалить интервал:
  ```python
  setting = await service.get(user.id)
  new_offsets = [m for m in setting.offsets_minutes if m != callback_data.minutes]
  await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
  setting = await service.get(user.id)
  await query.message.edit_text(_format_menu_text(setting), reply_markup=keyboards.reminders_menu_kbd(setting))
  await query.answer()
  ```
  - Удаление не валидируется (пустой список — валидное состояние), `service.update` примет.

### Step 6 — Тексты

- [ ] **В `src/bot/texts.py`** добавить (обновить `__all__`):
  - `REMINDERS_HEADER = "🔔 <b>Напоминания</b>"`
  - `REMINDERS_STATUS_ENABLED = "Статус: <b>✅ включены</b>"`
  - `REMINDERS_STATUS_DISABLED = "Статус: <b>🔕 выключены</b>"`
  - `REMINDERS_LIST_EMPTY = "Список интервалов пуст. Добавьте, за какое время напоминать."`
  - `REMINDERS_LIST_HEADER = "Вы получаете напоминания за:"`
  - `REMINDERS_HINT_DISABLED = "Чтобы получать напоминания, включите их кнопкой ниже."`
  - `REMINDERS_ADD_PROMPT = "Выберите пресет или введите свой:"`
  - `REMINDERS_ASK_CUSTOM = "Пришлите интервал текстом. Форматы: <code>15m</code>, <code>1h</code>, <code>2d</code> или число минут.\n\nМинимум — 5 минут, максимум — 7 дней (10080 минут)."`
  - `REMINDERS_INVALID_INPUT = "Не понял формат. Попробуйте: <code>15m</code> / <code>1h</code> / <code>2d</code> или просто число минут (5–10080)."`
  - `REMINDERS_ADDED = "✅ Добавлено: {humanized}."`
  - `REMINDERS_ERR_TOO_MANY = "У вас уже максимум интервалов (5). Удалите ненужный перед добавлением."`
  - `REMINDERS_ERR_DUPLICATE = "Такой интервал уже есть."`
  - `REMINDERS_ERR_BELOW_MINIMUM = "Минимальный интервал — 5 минут."`
- [ ] **Helper `_format_menu_text(setting: ReminderSetting) → str`** в router'е:
  - Заголовок `REMINDERS_HEADER`.
  - Статус (enabled / disabled).
  - Если enabled и offsets есть — `REMINDERS_LIST_HEADER` + по строке «• {humanized}» для каждого.
  - Если enabled и offsets пусто — `REMINDERS_LIST_EMPTY`.
  - Если disabled — `REMINDERS_HINT_DISABLED`.
  - Соединение — `"\n\n".join(...)`.

### Step 7 — Unit-тесты

`tests/unit/bot/routers/test_reminders_handler.py` — mock-based, ~12 тестов:

- [ ] **`cmd_reminders`:**
  - `test_cmd_reminders_unauthenticated_returns_message` (декоратор)
  - `test_cmd_reminders_blocked_returns_message` (декоратор)
  - `test_cmd_reminders_enabled_with_offsets_renders_list`
  - `test_cmd_reminders_disabled_renders_hint`
- [ ] **`on_toggle_reminders`:**
  - `test_on_toggle_inverts_enabled`
- [ ] **`on_add_offset` / `on_preset_offset`:**
  - `test_on_add_offset_shows_presets`
  - `test_on_preset_offset_adds_to_list`
  - `test_on_preset_offset_too_many_alerts` (мокаем `service.update` → `InvalidReminderOffsetsError("too many offsets")`)
- [ ] **`on_custom_offset` / `on_custom_offset_input`:**
  - `test_on_custom_offset_sets_state_and_asks_input`
  - `test_on_custom_offset_input_valid_adds_and_clears_state`
  - `test_on_custom_offset_input_invalid_keeps_state_asks_again`
- [ ] **`on_remove_offset`:**
  - `test_on_remove_offset_removes_from_list`

Дополнительно — **изолированные тесты parser'а** в `tests/unit/bot/test_reminders_parser.py`:

- [ ] `test_parse_offset_minutes_no_suffix` (`"15"` → 15)
- [ ] `test_parse_offset_minutes_m_suffix` (`"15m"`, `"15M"` → 15)
- [ ] `test_parse_offset_hours` (`"1h"` → 60, `"3H"` → 180)
- [ ] `test_parse_offset_days` (`"2d"` → 2880)
- [ ] `test_parse_offset_below_minimum_returns_none` (`"3"` → None)
- [ ] `test_parse_offset_above_maximum_returns_none` (`"20000"` → None, `"8d"` → None)
- [ ] `test_parse_offset_invalid_format_returns_none` (`"abc"`, `"1.5h"`, `""`, `"15z"` → None)
- [ ] `test_parse_offset_whitespace_tolerated` (`"  15  "`, `" 15m "` → 15)

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit (~20 новых).
- [ ] `uv run pytest tests/integration -m integration` — без падений (новых integration-тестов нет).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):** `/reminders` → меню с дефолтным `[1440, 60]`; «🔕 Выключить» → меняется статус; обратно «🔔 Включить»; «➕ Добавить интервал» → пресет «15 минут» → добавлен; снова «➕» → «✍️ Свой ввод» → «90m» → «1 ч 30 мин»; «➕» → «1 час» → «Такой интервал уже есть»; «🗑 1 ч» → удалён; добавить 6-й — alert «уже максимум».
- [ ] Ветка `feature/TASK-015-reminders`, Conventional Commits:
  - `feat(bot): EditingReminders FSM state`
  - `feat(bot): reminders callback data + keyboards + humanize_minutes`
  - `feat(bot): parse_offset helper (15m/1h/2d/raw)`
  - `feat(bot): reminders router — toggle/add/preset/custom/remove`
  - `feat(texts): reminders ui constants`
  - `test(bot): reminders handler + parse_offset tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-015-report.md`, задача → `handoff/archive/TASK-015-reminders/task.md`.

## Артефакты

```
+ src/bot/_reminders_parser.py                          # parse_offset (или встроенный)
* src/bot/states.py                                     # +EditingReminders
* src/bot/callbacks.py                                  # +6 callback classes
* src/bot/keyboards/__init__.py                         # +reminders_menu_kbd, reminders_add_kbd, humanize_minutes
* src/bot/texts.py                                      # +12 констант
* src/bot/routers/reminders.py                          # все handler'ы + _format_menu_text + _format_error
+ tests/unit/bot/routers/test_reminders_handler.py      # ~12 тестов
+ tests/unit/bot/test_reminders_parser.py               # 8 тестов парсера
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Настройка напоминаний»
- [src/shared/services/reminder.py](../../src/shared/services/reminder.py) — готовый сервис
- [src/shared/models/reminder_setting.py](../../src/shared/models/reminder_setting.py) — модель
- [src/shared/exceptions.py](../../src/shared/exceptions.py) — `InvalidReminderOffsetsError`
- [src/bot/routers/prediction.py](../../src/bot/routers/prediction.py) — образец FSM-handler с декоратором
- [src/bot/routers/my.py](../../src/bot/routers/my.py) — образец menu-render через edit_text

## Подсказки исполнителю

- **`ReminderSetting` всегда существует у регистрированного `User`** — это инвариант от TASK-011 (`UserService.register_or_authenticate` создаёт дефолтный `ReminderSetting(enabled=True, offsets_minutes=[1440, 60])`). Поэтому в handler'ах после `assert user is not None` можно `assert setting is not None`. Если когда-нибудь появится legacy user без settings — это бага, и пусть валится явным `AssertionError`.
- **`service.update(enabled=False, offsets_minutes=[1440, 60])` НЕ удаляет интервалы**, просто меняет `enabled`. Когда пользователь включит обратно — увидит те же интервалы. Это поведение по спеке (`docs/04-bot-flows.md` edge cases: «настройки сохраняются на момент повторного включения»).
- **`InvalidReminderOffsetsError`** содержит сообщение типа `"too many offsets: 6 (max 5)"`, `"duplicate offsets"`, `"offset 3 below minimum 5"`. Сейчас простейший `_format_error` сделает match по подстроке (`"too many"` / `"duplicate"` / `"below minimum"`). **Если станет лимит** — добавлю в `InvalidReminderOffsetsError` поле `reason: Literal["too_many", "duplicate", "below_minimum"]` в отдельной задаче (как у `EventNotPredictableError`). Сейчас YAGNI.
- **`F.text` фильтр в `EditingReminders.adding_offset` handler'е** — не ловит контакты, фотки, стикеры. Если пользователь шлёт не текст в этом состоянии — handler не сработает, callback просто проигнорируется. Это приемлемо; альтернатива — отдельный fallback handler с `F.~text` + reply «пришлите текст», но это лишняя ветка.
- **Маркер выключенных напоминаний.** Если `enabled=False`, скрываем `add` / `remove`-кнопки. Это упрощает UI: пользователь сначала должен включить, потом настраивать. Альтернатива (показать список и позволить редактировать в выключенном виде) — гибче, но визуально шумнее. На MVP — выбираем простоту.
- **`humanize_minutes(90)`** должен вернуть `"1 ч 30 мин"`, а не `"90 мин"`. Покрывай этот случай тестом (если не выделяешь в отдельный module — то inline в `test_reminders_handler.py`).
- **`logger.info("bot.reminders.toggle", user_id=..., new_enabled=...)`** и аналогичные structured-логи — в стиле других router'ов. Без user-data в логах (минут не считаются PII, но привычка).
- **state.clear() в `cmd_reminders`** — на случай, если пользователь застрял в `adding_offset` (написал `/reminders` вместо текста). По прецеденту `cmd_start` (`/start` всегда сбрасывает FSM).
- **`InaccessibleMessage` фолбэк для `query.message`** — паттерн `isinstance(query.message, Message)` уже использован в events.py / prediction.py / my.py. Применяй так же.

## Что НЕ делать

- Не добавлять методы в `ReminderService` — всё нужное есть.
- Не вводить новые доменные исключения / поля в `InvalidReminderOffsetsError` — match по строке достаточен (если окажется тесно — рефакторим в отдельной задаче).
- Не делать pagination интервалов — максимум 5, всегда влезают.
- Не показывать «удалить интервал» при `enabled=False` — упрощение UI.
- Не делать integration-тесты handler'а с реальной БД — mock-based достаточно.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не добавлять зависимости.
- Не зеркалить в Drive вручную — это зона cowork.
