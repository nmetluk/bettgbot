# Brief — task-012-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-012 и подготовить следующий шаг.

## Контекст

Локальный агент закрыл TASK-012 за 9 коммитов в одной фиче-ветке. Каталог событий в боте работает: пользователь жмёт «📅 Все события» (или `/events`) → видит категории с количеством активных событий + pseudo-«🗂 Все категории» → жмёт категорию → список событий с пагинацией (`PAGE_SIZE=7`, `‹/›`) → жмёт событие → карточка с описанием, дедлайном, исходами и опциональной строкой «✅ Ваш прогноз». «🔙 К событиям» / «🔙 К категориям» возвращают по навигации. Кнопка «Сделать прогноз» в карточке отсутствует — её добавит TASK-013.

Минимальный `CategoryService` (read-only) добавлен как обёртка над `CategoryRepository`. CRUD — в TASK-021 (admin). `EventService.list_categories_with_counts` — один SQL с `LEFT JOIN event` + `count(*) FILTER (WHERE published AND NOT archived)`. Типизированные callback'и в `src/bot/callbacks.py` через `aiogram.filters.callback_data.CallbackData` с короткими префиксами (`c`, `e`, `cl`). Auth-helper `_check_access` пока inline в handler'е.

148 unit/integration тестов, mypy strict зелёный, четыре CI job'а зелёных. PR [#32](https://github.com/nmetluk/bettgbot/pull/32) → squash `750f5b2`. Pre-task cleanup PR [#31](https://github.com/nmetluk/bettgbot/pull/31).

Полный отчёт — [`handoff/outbox/TASK-012-report.md`](../../handoff/outbox/TASK-012-report.md).

## Что сделано в этой сессии

- Приняты решения по пяти открытым вопросам — четыре «keep», одно «change»:
  - **Keep** — `EventService.list_categories_with_counts` остаётся в `EventService` (не переносится в `CategoryService`). EventService уже композирует Event/Outcome/Prediction/AuditLog; один SQL с join'ом проще, чем инъекция `EventRepository` в `CategoryService`.
  - **Keep** — `PAGE_SIZE = 7` остаётся локальной константой в `events.py`. Вынесем в `src/bot/_consts.py`, когда повторится; в TASK-013 пагинация не нужна (FSM прогноза работает с одним событием).
  - **Change** — `_check_access` inline-helper выносится в декоратор `@require_active_user` в `src/bot/auth.py` в **Step 1 TASK-013**. Триггер — четвёртое использование шаблона (3 callback handler'а в `events.py` + минимум 4 новых в `prediction.py`). Правило тройки соблюдено.
  - **Keep** — `events_in_category_kbd` с `adjust(*layout)` остаётся как есть. Работает, тесты зелёные, переписывание на `.row(...)` — refactor без выигрыша.
  - **Keep** — UTC-форматирование datetime в карточке без локализации. На MVP норм; i18n+TZ — отдельная задача после согласования источника TZ пользователя.
- Обновлён [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (закрытие TASK-012, новые шаги TASK-013 → TASK-014 → TASK-015).
- Добавлена строка в [`state/DECISIONS.md`](../../state/DECISIONS.md) про вынос `_check_access` в декоратор.
- Сформирована задача [`handoff/inbox/TASK-013-prediction-flow.md`](../../handoff/inbox/TASK-013-prediction-flow.md) — FSM «Сделать прогноз» с entry-point из карточки события.

## Что не сделано / отложено

- **Прямой entry-point из главного меню «🎯 Сделать прогноз» / `/predict`** с пропуском карточки события — в TASK-013 этот entry-point будет вести через каталог + карточку (один лишний клик от спеки `docs/04-bot-flows.md`). Если UX покажет, что extra-клик мешает, — отдельной TASK-013a введём `EventForPredictCb` и параллельные клавиатуры. Зафиксировано как open question TASK-013.
- **`src/bot/_consts.py`** не создаём (правило тройки для `PAGE_SIZE`).
- **«✅ Сбылся / ❌ Нет» в карточке архивных событий** — это TASK-014 (Мои прогнозы → Архив), там же агрегатная статистика.

## Следующие шаги

1. Владелец запускает локальный Claude Code на TASK-013.
2. Локальный агент делает pre-task cleanup PR (правки этой сессии + накопленные правки `CLAUDE.md` и `handoff/README.md` про «Push обязателен» и «Зеркало в Google Drive»), мёрджит, потом начинает TASK-013.
3. После TASK-013 — TASK-014 (Мои прогнозы: активные/архив + статистика пользователя).
4. После TASK-014 — TASK-015 (Настройка напоминаний: FSM добавления/удаления интервалов).
