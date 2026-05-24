---
id: TASK-014
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - docs/08-conventions.md
  - src/shared/services/prediction.py
  - src/shared/services/stats.py
  - src/bot/routers/events.py
priority: high
estimate: L
---

# TASK-014: раздел «📋 Мои прогнозы» — активные / архив + статистика

## Контекст

Четвёртый реальный handler. После TASK-013 пользователь умеет сделать прогноз; теперь он должен видеть список своих прогнозов и общую статистику. Раздел открывается из главного меню («📋 Мои прогнозы») или командой `/my`. Внутри — две вкладки: **🟢 Активные** (прогнозы по событиям с `is_archived = false`) и **📦 Архив** (по архивным). Тап на конкретный прогноз → карточка события (через существующий helper `render_event_card`). Под архивом отображается сводная статистика пользователя — `📊 {correct} / {total} ({percent}%)` через готовый `StatsService.user_stats`.

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) — раздел «Мои прогнозы»: вкладки, шаблоны карточек, статистика, тап → карточка события.
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — `Prediction(user_id, event_id, outcome_id, is_correct, updated_at)`; `Event.is_archived`, `result_outcome_id`.
- [`src/shared/services/prediction.py`](../../src/shared/services/prediction.py) — `list_active_by_user(user_id, offset, limit)`, `list_archived_by_user(user_id, offset, limit)` уже готовы.
- [`src/shared/services/stats.py`](../../src/shared/services/stats.py) — `StatsService.user_stats(user_id) -> tuple[int, int, float]` (correct, total, percent) уже готов.
- [`src/bot/routers/events.py`](../../src/bot/routers/events.py) — `render_event_card(query, event_id, back_category_id, user, session)` экспортируется. **Будем расширять** его сигнатуру параметром `back` для поддержки возврата «🔙 К моим прогнозам».
- [`src/bot/callbacks.py`](../../src/bot/callbacks.py) — стиль типизированных callback'ов через `aiogram.filters.callback_data.CallbackData` с короткими префиксами.

Серверной логики добавлять **не нужно** — все методы есть. Задача чисто bot-layer'а.

## Перед стартом — pre-task cleanup PR

Перед основной работой — стандартный pre-task cleanup PR ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). В `origin/main` накопились правки cowork:

- [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) — закрытие TASK-013, новый «Следующий шаг» TASK-014, добавлена строка про Drive-зеркало.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — 6 новых строк (5 решений по review TASK-013 + Drive-зеркало через MCP).
- [`handoff/README.md`](../README.md) — секция «Зеркало в Google Drive» переписана с реальным механизмом через MCP-коннектор (триггеры, таблица «что зеркалится», поиск папки по имени).
- Новая сессия [`sessions/2026-05-23-12-task-013-review/`](../../sessions/2026-05-23-12-task-013-review/).

Упакуй в `chore/post-TASK-013-cowork-cleanup`, открой PR `chore(handoff): post-TASK-013 review by cowork`, замерджи. После — ветка `feature/TASK-014-my-predictions` от свежего `main`.

## Цель

Пользователь видит свои прогнозы в двух вкладках с пагинацией, может тапнуть прогноз для просмотра карточки события, видит свою общую статистику. Покрыто mock-based unit-тестами. `render_event_card` расширен параметром «back», чтобы кнопка «🔙» возвращала туда, откуда пришёл пользователь (каталог категорий — из events flow; «Мои прогнозы» — из my flow).

## Definition of Done

### Step 1 — Расширение `render_event_card` параметром «back»

Параметр `back_category_id: int | None` сейчас управляет одной кнопкой возврата (callback `CategoryCb`). Для TASK-014 нужна альтернативная кнопка возврата (callback `MyTabCb`). Делаем расширяемо.

- [ ] **В `src/bot/keyboards/__init__.py`** изменить сигнатуру `event_card_kbd`:
  ```python
  from aiogram.filters.callback_data import CallbackData

  def event_card_kbd(
      *,
      event_id: int,
      can_predict: bool,
      has_prediction: bool,
      back_button: tuple[str, CallbackData],
  ) -> InlineKeyboardMarkup:
  ```
  - Старый параметр `back_category_id` удаляется. Вместо него — `back_button: tuple[str, CallbackData]` (текст кнопки + callback).
  - Внутри `event_card_kbd`: «🎯 Сделать прогноз» / «✏️ Изменить прогноз» (если `can_predict`) первой кнопкой, затем `builder.button(text=back_button[0], callback_data=back_button[1])`.
  - Все вызовы `event_card_kbd` (в `render_event_card`) и `event_card_kbd` от `predict_cancel` flow обновляются.
- [ ] **В `src/bot/routers/events.py`** изменить сигнатуру `render_event_card`:
  ```python
  async def render_event_card(
      query: CallbackQuery,
      event_id: int,
      back_button: tuple[str, CallbackData],
      user: User,
      session: AsyncSession,
  ) -> None:
  ```
  - Внутри — `event_card_kbd(event_id=..., can_predict=..., has_prediction=..., back_button=back_button)`.
- [ ] **В существующих местах вызова `render_event_card`:**
  - `on_event` (events.py) передаёт `back_button=("🔙 К событиям", CategoryCb(category_id=callback_data.back_category_id, page=0))`.
  - `on_predict_cancel` (prediction.py) сохраняет то же поведение: передаёт `back_button` с `CategoryCb`, восстановленным из `PredictCancelCb.back_category_id`.
- [ ] **`PredictCancelCb`** не меняется (он уже несёт `back_category_id`).

### Step 2 — Новые callback-data классы

- [ ] **В `src/bot/callbacks.py`** добавить:
  ```python
  from typing import Literal


  MyTab = Literal["active", "archive"]


  class MyTabCb(CallbackData, prefix="m"):
      """Переключение вкладок «Мои прогнозы» + пагинация."""

      tab: MyTab
      page: int = 0


  class MyPredictionCb(CallbackData, prefix="mp"):
      """Тап на прогноз → карточка события. Хранит `tab` для возврата."""

      event_id: int
      tab: MyTab  # для рендера «🔙 К моим прогнозам» с правильным табом
  ```
  - Префиксы коротки (`m`, `mp`). Лимит callback_data — 64 байта.
- [ ] Обнови `__all__`.

### Step 3 — Клавиатуры

- [ ] **`my_predictions_kbd(predictions, *, tab, page, has_prev, has_next) → InlineKeyboardMarkup`:**
  - По одной кнопке на прогноз: `text=f"{event.title} — {event.starts_at:%d.%m %H:%M}"`, callback `MyPredictionCb(event_id=prediction.event_id, tab=tab)`. Для архива можно дополнить эмодзи `✅`/`❌`/`⏳` (по `is_correct`), но это deferred — на первом проходе текст без эмодзи. **Решай сам на месте.**
  - Затем ряд с двумя таб-кнопками: «🟢 Активные» и «📦 Архив». Та, что соответствует текущей `tab`, помечена маркером (см. подсказку); другая — переключатель (`MyTabCb(tab=other_tab, page=0)`).
  - Затем пагинация `‹/›` (только если `has_prev` / `has_next`), callback `MyTabCb(tab=tab, page=page-1 / page+1)`.
  - Последняя кнопка — «🔙 В меню» (`MainMenuCb()`, см. Step 4) или просто без callback'а (ReplyKeyboard главного меню всегда показано пользователю — кнопка «🔙» избыточна?). **Решай:** если ReplyKeyboard внизу постоянно показывает «📋 Мои прогнозы» и другие пункты, отдельная inline-кнопка «🔙 В меню» избыточна. Я бы её **не добавлял**. Когда пользователь захочет уйти — он жмёт reply-кнопку.
  - `builder.adjust(...)`-разметка: 1 на каждый прогноз, потом 2 для табов, потом 1-2 для пагинации.
- [ ] **Текст под пагинацией / в шапке** — отдельным сообщением или в этом же. Простейший подход: один `edit_text(title + lines + stats_if_archive, reply_markup=kbd)`. То есть всё в одном тексте.
- [ ] Обнови `__all__`.

### Step 4 — Handler в `src/bot/routers/my.py`

- [ ] **Module docstring** «Router `/my` — раздел "Мои прогнозы" (TASK-014)».
- [ ] Импорты: `Command`, `F`, `Router`, `CallbackQuery`, `Message`, `AsyncSession`, `User`, `PredictionService`, `StatsService`, `EventService`, `keyboards`, `texts`, `MyTabCb`, `MyPredictionCb`, `CategoryCb`, `require_active_user`, `render_event_card`.
- [ ] `router = Router(name="my")`.
- [ ] **PAGE_SIZE = 7** локальной константой (как в events.py). По решению review TASK-012 — пока две точки, выносить рано.
- [ ] **`cmd_my`** — entry-point:
  ```python
  @router.message(Command("my"))
  @router.message(F.text == "📋 Мои прогнозы")
  @require_active_user
  async def cmd_my(message: Message, user: User | None, session: AsyncSession) -> None:
  ```
  - `assert user is not None`.
  - Дёргает `_render_my_tab(message, user, session, tab="active", page=0)`.
- [ ] **`on_my_tab`** — переключение вкладок / пагинация:
  ```python
  @router.callback_query(MyTabCb.filter())
  @require_active_user
  async def on_my_tab(
      query: CallbackQuery,
      callback_data: MyTabCb,
      user: User | None,
      session: AsyncSession,
  ) -> None:
  ```
  - `assert user is not None`.
  - Дёргает `_render_my_tab_edit(query, user, session, tab=callback_data.tab, page=callback_data.page)`.
- [ ] **Helper `_render_my_tab(message, user, session, tab, page)`** — рендер первичный (через `message.answer`):
  - `service = PredictionService(session)`.
  - `fetcher = service.list_active_by_user if tab == "active" else service.list_archived_by_user`.
  - `fetched = await fetcher(user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE + 1)`.
  - `predictions = list(fetched[:PAGE_SIZE])`; `has_next = len(fetched) > PAGE_SIZE`; `has_prev = page > 0`.
  - Если `predictions` пуст и `page == 0` → отправить `texts.MY_NO_ACTIVE` или `texts.MY_NO_ARCHIVE` (по табу) + клавиатура с переключателем табов (без списка). Return.
  - Иначе — собрать `lines: list[str]` по шаблонам `texts.MY_ROW_ACTIVE` / `texts.MY_ROW_ARCHIVE`. Для каждого — нужны `event.title`, `event.starts_at`, `outcome.label`, плюс для архива `event.result_outcome` и `prediction.is_correct`. **Важно:** `Prediction` не имеет relationship на `Outcome`, надо явно подгрузить — расширяем фетчер или делаем lazy-доп-запрос на каждом item'е. См. подсказку.
  - Заголовок: `texts.MY_HEADER_ACTIVE` / `texts.MY_HEADER_ARCHIVE`.
  - Если `tab == "archive"` — внизу добавляется статистика: `correct, total, percent = await StatsService(session).user_stats(user.id)`; форматировать через `texts.MY_STATS.format(correct=correct, total=total, percent=percent)`. Внутри active не показываем.
  - `text = header + "\n\n" + "\n\n".join(lines) + (stats_block if archive else "")`.
  - `await message.answer(text, reply_markup=keyboards.my_predictions_kbd(predictions, tab=tab, page=page, has_prev=has_prev, has_next=has_next))`.
- [ ] **Helper `_render_my_tab_edit(query, user, session, tab, page)`** — то же, но через `query.message.edit_text(...)` + `query.answer()`. **Не дублируй логику** — фактор out в общий helper, который возвращает `(text, kbd)` и из вызывающего делать `answer` или `edit_text`. Или — параметризовать reply mechanism через callback.
- [ ] **`on_my_prediction`** — открытие карточки события:
  ```python
  @router.callback_query(MyPredictionCb.filter())
  @require_active_user
  async def on_my_prediction(
      query: CallbackQuery,
      callback_data: MyPredictionCb,
      user: User | None,
      session: AsyncSession,
  ) -> None:
  ```
  - `assert user is not None`.
  - Кнопка «🔙» в карточке должна вести обратно в этот же таб: `back_button = ("🔙 К моим прогнозам", MyTabCb(tab=callback_data.tab, page=0))`. Возврат не на ту же страницу (page=N), а на первую — это компромисс ради простоты; иначе нужно нести `page` через MyPredictionCb (а это пляска с лимитом callback_data). На MVP ОК.
  - `await render_event_card(query, callback_data.event_id, back_button, user, session)`.

### Step 5 — Тексты

- [ ] **В `src/bot/texts.py`** добавить (обновить `__all__`):
  - `MY_HEADER_ACTIVE = "🟢 <b>Активные прогнозы</b>"`
  - `MY_HEADER_ARCHIVE = "📦 <b>Архив прогнозов</b>"`
  - `MY_NO_ACTIVE = "У вас пока нет активных прогнозов.\n\nЗайдите в «📅 Все события» и сделайте свой первый прогноз."`
  - `MY_NO_ARCHIVE = "Архив пуст. Прогнозы попадут сюда, когда события завершатся и админ зафиксирует итоги."`
  - `MY_ROW_ACTIVE` — шаблон строки активного прогноза:
    ```python
    MY_ROW_ACTIVE = (
        "⚽ <b>{title}</b>\n"
        "🗓 Старт: {starts_at_fmt}\n"
        "🎯 Ваш выбор: «{outcome_label}»\n"
        "⏳ Дедлайн: {close_at_fmt}"
    )
    ```
  - `MY_ROW_ARCHIVE` — шаблон строки архивного:
    ```python
    MY_ROW_ARCHIVE = (
        "⚽ <b>{title}</b> {status_emoji}\n"
        "🗓 Прошло: {starts_at_fmt}\n"
        "🎯 Ваш выбор: «{outcome_label}»\n"
        "🏁 Итог: «{result_label}»"
    )
    ```
    - `status_emoji`: `✅` если `is_correct == True`, `❌` если `False`, `⏳` если `None` (итог зафиксирован, но `is_correct` ещё не пересчитан — теоретически не должно случаться, но defensive).
    - Если `result_label is None` (теоретически невозможно при архиве — но defensive) → `result_label = "—"`.
  - `MY_STATS = "\n\n📊 Ваша статистика: <b>{correct}</b> / {total} ({percent}%)"` (с переводом строки в начале — отделяется от списка прогнозов).
  - Кнопочные тексты (`🟢 Активные`, `📦 Архив`, `‹`, `›`) — в `keyboards/__init__.py` хардкодом.

### Step 6 — Unit-тесты

`tests/unit/bot/routers/test_my_handler.py` — mock-based, как в `test_events_handler.py`:

- [ ] **`cmd_my`:**
  - `test_cmd_my_unauthenticated_returns_alert` (декоратор)
  - `test_cmd_my_blocked_returns_alert` (декоратор)
  - `test_cmd_my_no_predictions_sends_no_active`
  - `test_cmd_my_lists_active_predictions`
- [ ] **`on_my_tab`:**
  - `test_on_my_tab_switches_to_archive_renders_stats`
  - `test_on_my_tab_archive_empty_shows_no_archive_without_stats` (или со «статистика 0/0»?)
  - `test_on_my_tab_pagination_renders_next_page`
- [ ] **`on_my_prediction`:**
  - `test_on_my_prediction_calls_render_event_card_with_back_to_my`
  - **Pattern:** замокать `render_event_card` через `monkeypatch.setattr("src.bot.routers.my.render_event_card", AsyncMock())`. Проверить, что вызван с правильным `back_button`.

Минимум — 8-10 тестов. Все mock-based, integration не нужен (PredictionService + StatsService покрыты в TASK-009).

### Step 7 — Регрессия по существующим тестам

- [ ] `tests/unit/bot/routers/test_events_handler.py` — после переписывания `render_event_card` под новый параметр `back_button`, существующие тесты могут сломаться. Фикси тесты (не handler) под актуальную сигнатуру: проверяй, что в `event_card_kbd` передаётся `back_button=("🔙 К событиям", CategoryCb(...))`.
- [ ] `tests/unit/bot/routers/test_prediction_handler.py` — `on_predict_cancel` тоже использует `render_event_card`. Если тест проверяет `back_category_id` — обнови на `back_button`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit (~10-12 новых тестов).
- [ ] `uv run pytest tests/integration -m integration` — без падений (новых integration-тестов нет).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):** `make up && make migrate`, создать в БД 2-3 события с разными статусами (активное / архивное со СБЫЛСЯ / архивное с НЕТ), сделать прогнозы вручную или через бота, проверить `/my` в Telegram: активные → видны; «📦 Архив» → видны с эмодзи `✅/❌`; статистика снизу; тап на прогноз → карточка события; «🔙 К моим прогнозам» → возврат с правильным табом.
- [ ] Ветка `feature/TASK-014-my-predictions`, Conventional Commits:
  - `refactor(bot): event_card_kbd принимает back_button (tuple)`
  - `feat(bot): MyTabCb + MyPredictionCb callback data`
  - `feat(bot): my_predictions_kbd + texts`
  - `feat(bot): my router — tabs, pagination, stats, event card open`
  - `test(bot): my handler tests + регрессия events/prediction`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-014-report.md`, задача → `handoff/archive/TASK-014-my-predictions/task.md`.

## Артефакты

```
* src/bot/keyboards/__init__.py                  # event_card_kbd: back_category_id → back_button; +my_predictions_kbd
* src/bot/callbacks.py                           # +MyTabCb, MyPredictionCb
* src/bot/texts.py                               # +6 констант
* src/bot/routers/events.py                      # render_event_card: back_category_id → back_button; on_event обновлён
* src/bot/routers/prediction.py                  # on_predict_cancel передаёт back_button
* src/bot/routers/my.py                          # cmd_my + on_my_tab + on_my_prediction + helpers
+ tests/unit/bot/routers/test_my_handler.py      # ~10 тестов
* tests/unit/bot/routers/test_events_handler.py  # регрессия под новый back_button
* tests/unit/bot/routers/test_prediction_handler.py # регрессия под новый back_button
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Мои прогнозы»
- [docs/03-data-model.md](../../docs/03-data-model.md) — `Prediction`, `Event.result_outcome_id`
- [src/shared/services/prediction.py](../../src/shared/services/prediction.py) — `list_active_by_user` / `list_archived_by_user` готовы
- [src/shared/services/stats.py](../../src/shared/services/stats.py) — `user_stats(user_id) -> (correct, total, percent)` готов
- [src/bot/routers/events.py](../../src/bot/routers/events.py) — `render_event_card`, образец паттернов handler'ов
- [src/bot/routers/prediction.py](../../src/bot/routers/prediction.py) — образец FSM-less handler с декоратором
- [tests/unit/bot/routers/test_events_handler.py](../../tests/unit/bot/routers/test_events_handler.py) — образец mock-тестов

## Подсказки исполнителю

- **Подгрузка `outcome` для строки прогноза.** `Prediction` в текущей модели имеет FK `outcome_id`, но в репозитории `list_active_by_user` / `list_archived_by_user` возвращают чистые `Prediction` без eager-load'а `Outcome` / `Event`. Простейший путь — на каждом элементе списка дёрнуть `EventService.get_event(event_id, with_outcomes=True)` для получения и `Event`, и его `Outcome`. Это N+1 SQL на N прогнозов в списке (PAGE_SIZE=7 → 7 запросов). Для MVP **приемлемо**. Если в TASK-014-review увидим, что это горячая точка — добавим в `PredictionRepository` метод `list_*_by_user_with_relations` с `selectinload(Event)` и `selectinload(Event.outcomes)`. Зафиксирую как технический долг в BACKLOG после review.
- **Маркер активного таба.** Простейший способ — добавить unicode-маркер в текст кнопки текущего таба: `«🟢 Активные ✓»` vs `«📦 Архив»`. Жирность в кнопках Telegram не поддерживается; маркер `✓` — визуально читаемо.
- **`back_button: tuple[str, CallbackData]` vs dataclass.** Tuple — короче и без дополнительного типа. Минус — IDE не подсказывает имена. Для одного параметра, который не передаётся через многие слои — нормально. Если в TASK-015 потребуется четвёртая точка использования — рассмотрим выделение в `dataclass` / `NamedTuple`.
- **Mock'ать `render_event_card` в тестах `my.py`.** `from src.bot.routers.my import render_event_card` (импортирован через `from ..routers.events import render_event_card`). В тесте: `monkeypatch.setattr("src.bot.routers.my.render_event_card", AsyncMock())`. Не патчь на оригинальном пути — это разные имена в namespace модуля.
- **`MyTab = Literal["active", "archive"]`** — aiogram `CallbackData` поддерживает Literal-типы через pydantic. Сериализуется как просто строка. Десериализация валидирует.
- **Безопасный fallback при `is_archived` события прямо во время рендера.** Если архив, но `result_outcome_id is None` (админ заархивировал руками без фиксации итога — или automation TASK-018 архивировала по таймауту) — `status_emoji = "⏳"`, `result_label = "—"`. Это уместно для defensive UX.
- **Пагинация на нулевую страницу.** Кнопка `‹` показывается только если `page > 0`; при `page == 0` её нет. Кнопка `›` — только если `has_next` (получили `PAGE_SIZE + 1` элементов).
- **Возврат на `page=0` при тапе «🔙 К моим прогнозам».** Это упрощение (потеряли позицию пагинации, начали сначала). Можно нести `page` через `MyPredictionCb` — добавит ~2 байта, лимит 64 не превышен. **Решай сам на месте.** Если просто — без `page`. Если хочется UX — с `page`.
- **`logger.info("bot.my.tab_switched", ...)`** или подобное — структурное событие на переключение таба / пагинацию. Поля: `user_id`, `tab`, `page`. Не критично, но в стиле других router'ов.

## Что НЕ делать

- Не добавлять методы в `PredictionService` / `StatsService` — всё нужное есть.
- Не делать lazy-loading через ORM relationships вне репозиториев (правило `docs/08-conventions.md`: «без бизнес-логики в моделях»).
- Не выносить `PAGE_SIZE` в `src/bot/_consts.py` — пока две точки (events + my), правило тройки.
- Не вводить новые FSM-состояния — этот flow без FSM, всё через callback-data.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` (за пределами стандартного pre-task cleanup PR).
- Не добавлять зависимости.
- Не зеркалить вручную в Drive — это зона cowork-агента.
