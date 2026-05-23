---
task: TASK-012
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/32
branch: feature/TASK-012-events-handler
commits:
  - 0971d3d feat(services): CategoryService (read-only)
  - 377d979 feat(services): EventService.list_categories_with_counts
  - 227e39c feat(bot): typed callback data (CategoryCb, EventCb, CategoryListCb)
  - 130792e feat(bot): inline keyboards for events flow
  - d42a3b5 feat(texts): events-related UI constants
  - 58b5ad0 feat(bot): events router — categories, events list, event card
  - b13abcf test(services): CategoryService + list_categories_with_counts
  - 4387fed test(bot): events router tests
  - e55ad58 chore(handoff): mark TASK-012 in-progress
---

# Отчёт по TASK-012: handler «📅 Все события» — категории, список, карточка

## Сводка

Каталог событий в боте работает: пользователь жмёт «📅 Все события» (или `/events`) → видит список категорий с количеством активных событий + pseudo-«🗂 Все категории» → жмёт категорию → список событий с пагинацией (PAGE_SIZE=7, `‹/›`) → жмёт событие → карточка с описанием, дедлайном, исходами и опциональной строкой «✅ Ваш прогноз». «🔙 К событиям» / «🔙 К категориям» возвращают по навигации. Кнопка «Сделать прогноз» в карточке отсутствует — её добавит TASK-013 (там FSM).

Минимальный `CategoryService` (read-only) — обёртка над `CategoryRepository`. CRUD будет в TASK-021. `EventService.list_categories_with_counts` — один SQL: `SELECT category, count(event) FILTER (...) OUTER JOIN event GROUP BY category`. Категории с 0 активных событий включены в список (UX «событий пока нет»).

Типизированные callback'и в `src/bot/callbacks.py` через `aiogram.filters.callback_data.CallbackData` — короткие префиксы (`c`, `e`, `cl`) ради лимита 64 байта на `callback_data`. `CategoryCb` принимает `category_id: int | None` для pseudo-«все категории».

Auth-helper `_check_access(user)` inline в handler'е (`message.answer(deny)` или `query.answer(deny, show_alert=True)` — разные канвасы для сообщений и callback'ов). Когда дойдём до 4-го handler'а с тем же шаблоном — вынесем в middleware/декоратор.

Pre-task cleanup PR [#31](https://github.com/nmetluk/bettgbot/pull/31) свернул правки cowork (5 DECISIONS, sessions/2026-05-23-10).

## Изменённые файлы

```
+ src/shared/services/category.py                            # CategoryService
* src/shared/services/__init__.py                            # +CategoryService
* src/shared/services/event.py                               # +list_categories_with_counts
+ src/bot/callbacks.py                                       # CallbackData classes
* src/bot/keyboards/__init__.py                              # +3 фабрики inline-клавиатур
* src/bot/routers/events.py                                  # cmd_events + 3 callback handler
* src/bot/texts.py                                           # +5 констант
+ tests/integration/services/test_category_service.py        # 3
* tests/integration/services/test_event_service.py           # +3
+ tests/unit/bot/routers/test_events_handler.py              # 13
* handoff/inbox/TASK-012-events-handler.md → in-progress → archive
+ handoff/archive/TASK-012-events-handler/task.md
+ handoff/outbox/TASK-012-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    99 files already formatted
mypy src/shared src/bot          Success: no issues found in 53 source files
pytest                           148 passed in 9.01s

CI PR #32 — все четыре job'а зелёные:
  Lint (ruff)                     8s
  Typecheck (mypy)                17s
  Tests (pytest, unit)            18s
  Integration (alembic on real postgres)  39s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
make up && make migrate

uv run pytest -m "not integration" -v
uv run pytest tests/integration -m integration -v

# Ручная проверка в TG: создать категории/события в make db.psql,
# /start (или нажать кнопку), /events → меню.
uv run python -m src.bot.main
```

## Что не сделано / вынесено

1. **Кнопка «Сделать прогноз» в карточке** — TASK-013 (там же FSM выбора исхода)
2. **CRUD категорий в `CategoryService`** — TASK-021 (admin)
3. **TZ-конвертация datetime** — на MVP UTC (по `docs/04-bot-flows.md`)
4. **Integration-тесты handler'ов с aiogram-runtime** — DoD запрещает

## Открытые вопросы для проектировщика

1. **`EventService.list_categories_with_counts` импортирует Category-модель.** EventService теперь зависит от Category. Альтернатива — `CategoryService.list_with_event_counts` с инъекцией `EventRepository`. Согласуем?
2. **`PAGE_SIZE = 7` константа в `events.py`.** Если повторится в TASK-014 («Мои прогнозы») — вынесем в `src/bot/_consts.py`. Сейчас локально.
3. **Auth-helper `_check_access` inline в `events.py`.** Когда появится 4-й handler с тем же шаблоном (TASK-013 минимум) — вынесем в `RequireUserMiddleware` или decorator. Сейчас inline в одном файле.
4. **`InlineKeyboardBuilder.adjust(*layout)` сложный** в `events_in_category_kbd` — собираю layout `[1]*n + pagination + [1]`. Альтернатива — `builder.row(...)` для каждой группы. Перепишу при следующем рефакторинге.
5. **`UTC` форматирование datetime** в карточке без локализации. На MVP норм; i18n+TZ — отдельная задача.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-012: каталог событий в боте — `cmd_events` (categories + total), пагинация по событиям (PAGE_SIZE=7), карточка с outcomes и опциональной строкой «Ваш прогноз». `CategoryService` (read-only), `EventService.list_categories_with_counts` (1 SQL, OUTER JOIN + count FILTER). Типизированные `CallbackData` (CategoryCb/EventCb/CategoryListCb). 19 новых тестов. PR [#32](https://github.com/nmetluk/bettgbot/pull/32) → squash `750f5b2`. Pre-task cleanup [#31](https://github.com/nmetluk/bettgbot/pull/31).
```

## Метрики

- Файлов добавлено: 4 (CategoryService, callbacks, 2 теста)
- Файлов изменено: 5 (services/__init__, event, keyboards, events router, texts)
- Тестов добавлено: 19 (всего теперь 148: 73 unit + 4 migrations + 36 repos + 35 services)
- Время на выполнение: ~70 мин (включая cleanup PR, фикс `InaccessibleMessage` через isinstance-narrowing, ruff cleanup для unused vars)
