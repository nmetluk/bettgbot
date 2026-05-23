---
id: TASK-012
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - docs/08-conventions.md
  - src/shared/services/event.py
  - src/shared/repositories/category.py
priority: high
estimate: L
---

# TASK-012: handler «📅 Все события» — категории, список с пагинацией, карточка

## Контекст

Второй реальный handler — «каталог событий». Read-only пользовательский поток: пользователь нажимает кнопку «📅 Все события» (или шлёт `/events`) → видит список категорий с количеством активных событий → выбирает категорию → видит список событий в категории с пагинацией → тапает событие → видит карточку с описанием, дедлайном, исходами. Кнопка «Сделать прогноз» в карточке появится в TASK-013 (там — FSM).

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) — раздел «Все события», шаги 1–3 (категории → события → карточка); архивация скрывает события из активных списков; форматы карточек.
- [`docs/03-data-model.md`](../../docs/03-data-model.md) — `Event.is_published`, `is_archived`, `starts_at`, `predictions_close_at`, `metadata_`, отношения.
- [`src/shared/services/event.py`](../../src/shared/services/event.py) — `list_active`, `count_active`, `get_with_outcomes` уже есть.
- [`src/shared/repositories/category.py`](../../src/shared/repositories/category.py) — `list(active_only=True)`, `get_by_id`, `get_by_slug` уже есть.
- [`src/shared/services/`](../../src/shared/services/) — но **`CategoryService` ещё нет**. По конвенции handler не лезет в repository — нужно создать минимальный сервис.

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork: обновлённые `state/PROJECT_STATUS.md` и `state/DECISIONS.md` (5 новых записей), новая сессия `sessions/2026-05-23-10-task-011-review/`. Упакуй в `chore/post-TASK-011-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-012-events-handler` от свежего `main`.

## Цель

Пользователь может листать каталог событий в боте, фильтровать по категориям, пагинировать длинные списки, открывать карточку события и видеть всю публичную информацию о нём. «Сделать прогноз» button в карточке — стаб без активного callback'а (TASK-013 подключит). Незарегистрированные/заблокированные пользователи получают понятный отказ. Покрыто unit-тестами.

## Definition of Done

### Step 1 — `CategoryService` (минимум)

- [ ] **`src/shared/services/category.py`** — новый файл:
  - `class CategoryService` с конструктором `__init__(self, session: AsyncSession)`.
  - Методы (read-only, без commit):
    - `async def get_by_id(category_id: int) -> Category | None`
    - `async def get_by_slug(slug: str) -> Category | None`
    - `async def list_active() -> Sequence[Category]`
  - Module docstring + `__all__ = ["CategoryService"]`.
  - **CRUD-операции (`create`, `update`, `delete`) в этой задаче НЕ нужны** — добавим в TASK-021 (admin категории).
- [ ] **`src/shared/services/__init__.py`** — добавить `CategoryService` в re-export и `__all__`.

### Step 2 — `EventService.list_categories_with_counts`

- [ ] Добавить в `src/shared/services/event.py`:
  ```python
  async def list_categories_with_counts(self) -> tuple[Sequence[tuple[Category, int]], int]:
      """Возвращает (список (категория, число_активных_событий), общее_число_по_всем_категориям).

      Используется в bot для «📅 Все события» — рендер списка категорий с цифрой в скобках
      и pseudo-пункт «🗂 Все категории (N)».
      """
  ```
  - Реализация: один запрос с `LEFT JOIN event` + `GROUP BY category.id` + `count(*) FILTER (WHERE event.is_published AND NOT event.is_archived)`.
  - Возвращает только активные категории (`Category.is_active = true`), отсортированные по `sort_order, id`.
  - Категории с нулём активных событий — **включать** в список (пользователь может зайти и увидеть «событий пока нет», это нормально).
  - Общее число — сумма `int`-полей.
- [ ] Если `EventService` не должен лезть в `CategoryRepository` напрямую (он уже лезет в `OutcomeRepository`, так что прецедент есть) — норм, метод остаётся в `EventService`. Альтернатива — поместить в `CategoryService` с инъекцией `EventRepository`, тогда у CategoryService появляется зависимость от Event. Реши на месте; я предпочитаю **в `EventService`** (он уже знает про counts).

### Step 3 — Дополнения в `src/bot/keyboards/__init__.py`

- [ ] Новые функции-фабрики (с типизированной `CallbackData` — Step 4):
  - `categories_kbd(categories_with_counts: Sequence[tuple[Category, int]], total: int) -> InlineKeyboardMarkup`
    - По одной кнопке на категорию: `"{name} ({count})"`, callback `CategoryCb(category_id=cat.id, page=0)`.
    - Последняя кнопка — pseudo-«🗂 Все категории ({total})» — callback `CategoryCb(category_id=None, page=0)`. Используй `None` для «все», не `-1` (явно через `Optional[int]`).
  - `events_in_category_kbd(events: Sequence[Event], *, page: int, has_prev: bool, has_next: bool, category_id: int | None) -> InlineKeyboardMarkup`
    - По одной кнопке на событие: `"{title} — {starts_at:%d.%m %H:%M}"`, callback `EventCb(event_id=event.id, back_category_id=category_id)`.
    - Пагинация: `‹` (`PaginationCb(category_id=..., page=page-1, action="prev")`) если `has_prev`; `›` (action="next") если `has_next`. В одну строку.
    - Кнопка «🔙 К категориям» — callback `CategoryListCb()` (или `NavCb(target="categories")`).
  - `event_card_kbd(event_id: int, back_category_id: int | None, has_prediction: bool) -> InlineKeyboardMarkup`
    - Кнопка «🎯 Сделать прогноз» или «✏️ Изменить прогноз» (по `has_prediction`) — **stub** без callback'а на TASK-012 (TASK-013 подключит). Один из вариантов:
      - Не добавлять кнопку в TASK-012 вообще — карточка чисто read-only.
      - Добавить кнопку с заглушечным callback `PredictionStubCb()` и обработчиком, который отвечает alert «Скоро будет».
    - Я предпочитаю **не добавлять кнопку в TASK-012** — пусть TASK-013 явно её введёт. Карточка пока показывает только данные + «🔙 К событиям».
    - Кнопка «🔙 К событиям» — callback `CategoryCb(category_id=back_category_id, page=0)`.
- [ ] Все клавиатуры — `InlineKeyboardBuilder`, `.adjust(...)` для разметки в ряды.
- [ ] Подходящие импорты, расширить `__all__`.

### Step 4 — `src/bot/callbacks.py` (новый файл)

- [ ] Module docstring «Типизированные callback_data (aiogram CallbackData factory) для inline-клавиатур».
- [ ] Импорт `from aiogram.filters.callback_data import CallbackData`.
- [ ] Классы (короткие префиксы для экономии лимита 64 байт):
  ```python
  class CategoryCb(CallbackData, prefix="c"):
      category_id: int | None  # None = "все категории"
      page: int = 0

  class EventCb(CallbackData, prefix="e"):
      event_id: int
      back_category_id: int | None  # для кнопки "К событиям" из карточки

  class CategoryListCb(CallbackData, prefix="cl"):
      """Возврат на список категорий — без параметров."""
  ```
- [ ] Пагинация решается через `CategoryCb(page=...)` — отдельного PaginationCb не нужно. `page=0` для первой страницы, `page=N-1` для последней.
- [ ] `__all__` с явным списком.

### Step 5 — Handler в `src/bot/routers/events.py`

- [ ] Module docstring + `router = Router(name="events")`.
- [ ] **Auth-helper** (повторяется в каждом handler'е после `/start` — пока inline, не decorator):
  ```python
  def _check_access(user: User | None) -> str | None:
      """Возвращает текст для ответа, если доступа нет; None если ОК."""
      if user is None:
          return texts.NEED_START
      if user.is_blocked:
          return texts.ACCESS_DENIED
      return None
  ```
  Положи рядом с handler'ами в `events.py` (или в новый `src/bot/_auth.py` — на твоё усмотрение).
- [ ] **Handler `/events` + кнопка** «📅 Все события»:
  ```python
  @router.message(Command("events"))
  @router.message(F.text == "📅 Все события")
  async def cmd_events(message: Message, user: User | None, session: AsyncSession) -> None:
  ```
  - Auth-check (если нет — `message.answer(...)` + return).
  - `service = EventService(session)`; `cats, total = await service.list_categories_with_counts()`.
  - Если total == 0 — отправить `texts.NO_EVENTS_AT_ALL` (новая константа) + `keyboards.main_menu()`. Return.
  - Иначе — `message.answer(texts.CATEGORIES_PROMPT, reply_markup=keyboards.categories_kbd(cats, total))`.
- [ ] **Callback handler категории** (`CategoryCb`):
  ```python
  @router.callback_query(CategoryCb.filter())
  async def on_category(query: CallbackQuery, callback_data: CategoryCb, user: User | None, session: AsyncSession) -> None:
  ```
  - Auth-check (если нет — `query.answer(text, show_alert=True)` + return).
  - Page-size константа в модуле `PAGE_SIZE = 7` ([docs/04-bot-flows.md](../../docs/04-bot-flows.md): «по 5–7 на страницу»).
  - `service.list_active(category_id=..., offset=page*PAGE_SIZE, limit=PAGE_SIZE+1)` — `+1` чтобы понять, есть ли следующая страница.
  - `service.count_active(category_id=...)` — для пагинации (или для отображения «N событий»).
  - Если событий нет — отредактировать сообщение (или новое) `texts.NO_EVENTS_IN_CATEGORY` + кнопка «🔙 К категориям». Можно `query.message.edit_text(...)`.
  - Иначе — `events = first PAGE_SIZE`, `has_next = len(fetched) > PAGE_SIZE`, `has_prev = page > 0`. Отрендерить заголовок «Категория «{name}»: страница {page+1}/?» + `events_in_category_kbd(...)`.
  - `await query.answer()` (закрыть «часики»).
- [ ] **Callback handler возврата к категориям** (`CategoryListCb`):
  - Auth-check.
  - Снова получить cats+total, `query.message.edit_text(texts.CATEGORIES_PROMPT, reply_markup=keyboards.categories_kbd(cats, total))`.
  - `await query.answer()`.
- [ ] **Callback handler события** (`EventCb`):
  ```python
  @router.callback_query(EventCb.filter())
  async def on_event(query: CallbackQuery, callback_data: EventCb, user: User | None, session: AsyncSession) -> None:
  ```
  - Auth-check.
  - `event = await service.get_event(event_id, with_outcomes=True)`. Если None — `query.answer("Событие не найдено", show_alert=True)`. Return.
  - Если `event.is_archived` или not `event.is_published` — `query.answer("Событие недоступно", show_alert=True)`. Return. (Тех. ситуация при гонке: пока пользователь думал, админ архивировал/снял с публикации.)
  - Запрос имени категории (через `CategoryService.get_by_id`) — для шапки карточки.
  - **Проверить, есть ли у пользователя прогноз по этому событию** — для будущей кнопки. На TASK-012 — не показываем кнопку, но info-строку «✅ Ваш прогноз: ‘{label}’» в тексте карточки уже выводим, если прогноз есть. Это потребует `PredictionService.get_user_prediction(user_id, event_id)` — добавь в PredictionService, если нет (есть — `get_user_prediction` уже там).
  - Сформировать текст карточки по шаблону `texts.EVENT_CARD` (новая константа) — параметризованный `.format()`. Шаблон по [docs/04-bot-flows.md](../../docs/04-bot-flows.md):
    ```
    🏆 {category_name}
    ⚽ {title}

    {description, если есть}

    🗓 Начало: {starts_at:%d.%m.%Y %H:%M}
    ⏳ Приём прогнозов до: {predictions_close_at:%d.%m %H:%M}

    Возможные исходы:
    1) {outcome1.label}
    2) {outcome2.label}
    ...

    {если есть прогноз — "✅ Ваш прогноз: «{prediction_outcome.label}»"}
    ```
  - `query.message.edit_text(text, reply_markup=keyboards.event_card_kbd(event_id, back_category_id, has_prediction=has_pred))`.
  - `await query.answer()`.

### Step 6 — Дополнения в `src/bot/texts.py`

- [ ] Новые константы:
  - `CATEGORIES_PROMPT = "📅 Категории событий:"`
  - `NO_EVENTS_AT_ALL = "Сейчас активных событий нет. Загляните позже."`
  - `NO_EVENTS_IN_CATEGORY = "В этой категории пока нет активных событий."`
  - `EVENT_NOT_AVAILABLE = "Событие больше недоступно."` (для гонок при архивации/снятии с публикации)
  - `EVENT_CARD` — multi-line шаблон с placeholder'ами `{category_name}`, `{title}`, `{description_block}`, `{starts_at_fmt}`, `{close_at_fmt}`, `{outcomes_block}`, `{prediction_block}`. `description_block`/`prediction_block` — пустая строка или с переносом строки в зависимости от наличия данных (форматирование собирается в handler'е).
- [ ] Обнови `__all__`.

### Step 7 — Unit-тесты

`tests/unit/bot/routers/test_events_handler.py`:

- [ ] `test_cmd_events_no_categories_sends_no_events_at_all`
- [ ] `test_cmd_events_lists_categories_with_counts`
- [ ] `test_cmd_events_unauthenticated_sends_need_start`
- [ ] `test_cmd_events_blocked_sends_access_denied`
- [ ] `test_on_category_lists_events_with_pagination`
- [ ] `test_on_category_empty_shows_no_events_in_category`
- [ ] `test_on_category_back_navigates_to_category_list` (через `CategoryListCb`)
- [ ] `test_on_event_renders_card_without_prediction`
- [ ] `test_on_event_renders_card_with_user_prediction` (показывает «✅ Ваш прогноз»)
- [ ] `test_on_event_archived_returns_alert`
- [ ] `test_on_event_not_published_returns_alert`
- [ ] `test_on_event_not_found_returns_alert`

Используй mock'и `Message`, `CallbackQuery`, `EventService`, `CategoryService`, `PredictionService`. Не пиши integration-тесты с реальной БД для handler'ов — это не нужно.

`tests/integration/services/test_category_service.py`:

- [ ] `test_list_active_returns_only_active_sorted`
- [ ] `test_get_by_id_returns_none_for_missing`
- [ ] `test_get_by_slug_returns_correct`

`tests/integration/services/test_event_service.py` — расширить:

- [ ] `test_list_categories_with_counts_zero_events_categories_included`
- [ ] `test_list_categories_with_counts_counts_only_published_active`
- [ ] `test_list_categories_with_counts_total_matches_sum`

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая новые events-handler-тесты.
- [ ] `uv run pytest tests/integration -m integration` — без падений (новые CategoryService-тесты, расширенные EventService-тесты).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка локально (опц., не в DoD):** `make up && make migrate`, создай тестовых категорий/событий руками через `make db.psql`, запусти `uv run python -m src.bot.main`, проверь сценарий «📅 Все события» в Telegram.
- [ ] Ветка `feature/TASK-012-events-handler`, Conventional Commits:
  - `feat(services): CategoryService`
  - `feat(services): EventService.list_categories_with_counts`
  - `feat(bot): events router — categories, events list, event card`
  - `feat(bot): typed callback data + inline keyboards`
  - `feat(texts): events-related ui constants`
  - `test(services): CategoryService + list_categories_with_counts`
  - `test(bot): events router tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-012-report.md`, задача → `handoff/archive/TASK-012-events-handler/task.md`.

## Артефакты

```
+ src/shared/services/category.py              # CategoryService (3 методa)
* src/shared/services/__init__.py              # +CategoryService
* src/shared/services/event.py                 # +list_categories_with_counts
+ src/bot/callbacks.py                         # CategoryCb, EventCb, CategoryListCb
* src/bot/keyboards/__init__.py                # +categories_kbd, events_in_category_kbd, event_card_kbd
* src/bot/routers/events.py                    # cmd_events + 3 callback handler'а
* src/bot/texts.py                             # +5 констант
+ tests/integration/services/test_category_service.py
* tests/integration/services/test_event_service.py    # +3 теста на list_categories_with_counts
+ tests/unit/bot/routers/test_events_handler.py       # 12 тестов
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — раздел «Все события»
- [docs/03-data-model.md](../../docs/03-data-model.md) — поля Event/Category/Outcome
- [src/shared/services/event.py](../../src/shared/services/event.py)
- [src/shared/repositories/category.py](../../src/shared/repositories/category.py)
- [src/bot/routers/start.py](../../src/bot/routers/start.py) — образец паттернов handler'а

## Подсказки исполнителю

- **`CallbackData`** в aiogram 3 — `@dataclass`-like с `prefix` в `class CategoryCb(CallbackData, prefix="c"):`. Сериализуется как `"c:<id>:<page>"`. Лимит 64 байта — короткие префиксы важны.
- **`callback_data: CategoryCb`** в сигнатуре handler'а: aiogram автоматически парсит `query.data` по фильтру `CategoryCb.filter()` и пробрасывает типизированный объект.
- **`InlineKeyboardBuilder`**:
  ```python
  from aiogram.utils.keyboard import InlineKeyboardBuilder

  builder = InlineKeyboardBuilder()
  for cat, count in cats:
      builder.button(text=f"{cat.name} ({count})", callback_data=CategoryCb(category_id=cat.id, page=0))
  builder.button(text=f"🗂 Все категории ({total})", callback_data=CategoryCb(category_id=None, page=0))
  builder.adjust(1)  # по одной в ряд
  return builder.as_markup()
  ```
- **`query.message.edit_text(...)`** — заменяет сообщение, в которое нажали кнопку. Удобнее, чем новое сообщение каждый шаг.
- **`query.answer()`** — обязательный для callback'ов; без него «часики» крутятся 30 секунд у пользователя. Если хочешь alert — `query.answer("...", show_alert=True)`.
- **Optional `int | None` в CallbackData**: aiogram сериализует `None` как пустую строку `""`. При десериализации возвращает `None`. Это работает «из коробки» для типов `int | None`.
- **`count_active(category_id=None)`** уже есть и считает все опубликованные неархивные.
- **`list_categories_with_counts` через SQL:**
  ```python
  stmt = (
      select(Category, func.count(Event.id).filter(
          Event.is_published.is_(True),
          Event.is_archived.is_(False),
      ))
      .outerjoin(Event, Event.category_id == Category.id)
      .where(Category.is_active.is_(True))
      .group_by(Category.id)
      .order_by(Category.sort_order, Category.id)
  )
  ```
  Если sqlalchemy/mypy ругаются на `func.count(...).filter(...)` — раскрой через `func.sum(case((..., 1), else_=0))`.
- **`description_block` в карточке:** если `event.description` — `None` или пустая, передавай `description_block=""`; иначе `f"\n{event.description}\n"`. Это убирает лишние пустые строки.
- **`prediction_block`** аналогично: если прогноз есть — `f"\n✅ Ваш прогноз: «{outcome.label}»"`; иначе `""`.
- **Datetime форматирование** в строке — `event.starts_at.strftime("%d.%m.%Y %H:%M")`. Учти TZ: события у нас `timestamptz`, в БД хранятся в UTC, для пользователя возможно стоит отображать по TZ его страны… на MVP — UTC, добавим i18n+TZ позже.
- **Auth-check inline** в каждом handler'е — три строки. Когда будем повторяться в 4-м handler'е (TASK-013), вынесем в `RequireUserMiddleware` или в декоратор. Сейчас — inline без преждевременной абстракции.
- **«Сделать прогноз» button НЕ добавляй в карточку** в TASK-012. TASK-013 добавит её и подключит callback. Если в `event_card_kbd` единственная кнопка «🔙 К событиям» — это норм.

## Что НЕ делать

- Не реализовывать FSM «Сделать прогноз» — это TASK-013.
- Не делать CRUD категорий (`create`, `update`, `delete` в CategoryService) — это TASK-021.
- Не подключать кнопку «🎯 Сделать прогноз» с активным callback'ом — только когда дойдём до TASK-013.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не добавлять зависимости.
- Не делать integration-тесты bot-handler'ов с реальной aiogram-сетью — mock'и Message/CallbackQuery достаточны.
