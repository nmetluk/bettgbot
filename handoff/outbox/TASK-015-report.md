---
task: TASK-015
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/40
branch: feature/TASK-015-reminders
commits:
  - 0251e2b feat(bot): EditingReminders FSM state
  - 0637537 feat(bot): reminders callback data (6 классов)
  - a7fd87a feat(bot): parse_offset helper
  - 44d5101 feat(bot): reminders_menu_kbd + reminders_add_kbd + humanize_minutes
  - cc9e7ab feat(texts): reminders UI constants
  - 5cfac78 feat(bot): reminders router — toggle/add/preset/custom/remove
  - a525981 test(bot): parse_offset + reminders handler (20 тестов)
  - 09dea2c chore(handoff): take TASK-015 in progress, drop TASK-014 duplicate
---

# Отчёт по TASK-015: настройка напоминаний — toggle + интервалы + FSM

## Сводка

Пользователь открывает «🔔 Напоминания» (или `/reminders`) → видит статус и список интервалов; может переключить toggle, добавить интервал из 6 пресетов (15м/30м/1ч/3ч/12ч/1д) или ввести свой текстом (`15m` / `1h` / `2d` / `90`-минут — диапазон 5–10080), удалить интервал, отменить. Серверная логика — `ReminderService.update` (уже в TASK-009) с валидацией ≤5 / ≥5 минут / без дубликатов; handler ловит `InvalidReminderOffsetsError` и переводит в `REMINDERS_ERR_TOO_MANY` / `_DUPLICATE` / `_BELOW_MINIMUM`.

FSM `EditingReminders(adding_offset)` нужен только для текстового ввода. Toggle/preset/remove — без FSM, через callback'и. После валидного ввода — `state.clear()` и рендер обновлённого меню; после ошибки — state остаётся, пользователь может попробовать ещё раз. `cmd_reminders` сбрасывает FSM на входе (как `cmd_start`).

При `enabled=False` UI скрывает add/remove — сначала включи, потом настраивай.

Удалил parallel-инстанс-дубликат `handoff/inbox/TASK-014-my-predictions.md` (он попал в мой cleanup PR #39, потому что cowork положил его в inbox, не зная, что TASK-014 уже была выполнена другой CC-инстанцией и архивирована в PR #38).

Pre-task cleanup PR [#39](https://github.com/nmetluk/bettgbot/pull/39) свернул правки cowork (CLAUDE.md «Push обязателен», handoff/README.md про MCP-зеркало в Drive, 10 DECISIONS).

## Изменённые файлы

```
* src/bot/states.py                          # +EditingReminders
* src/bot/callbacks.py                       # +6 callback classes
+ src/bot/_reminders_parser.py               # parse_offset (15m/1h/2d/N min)
* src/bot/keyboards/__init__.py              # +humanize_minutes, reminders_menu_kbd, reminders_add_kbd
* src/bot/texts.py                           # +13 констант
* src/bot/routers/reminders.py               # 7 handler'ов + 2 helpers
+ tests/unit/bot/test_reminders_parser.py    # 8 параметризованных тестов
+ tests/unit/bot/routers/test_reminders_handler.py  # 12 тестов
- handoff/inbox/TASK-014-my-predictions.md   # дубликат parallel-CC, удалён
* handoff/inbox/TASK-015-reminders.md → in-progress → archive
+ handoff/archive/TASK-015-reminders/task.md
+ handoff/outbox/TASK-015-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    106 files already formatted
mypy src/shared src/bot          Success: no issues found in 55 source files
pytest -m "not integration"      146 passed in 1.32s
(integration не гонял локально — docker daemon не запущен; CI отработал)

CI PR #40 — все четыре job'а зелёные:
  Lint (ruff)                     11s
  Typecheck (mypy)                18s
  Tests (pytest, unit)            13s
  Integration (alembic on real postgres)  36s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
make up && make migrate

uv run pytest -m "not integration" -v
uv run pytest tests/integration -m integration -v

# Ручная проверка в TG:
# /reminders → видишь меню со [1440, 60] (1 д / 1 ч)
# 🔕 Выключить → меняется статус → 🔔 Включить
# ➕ → выбрать «15 минут» → добавлено
# ➕ → ✍️ Свой ввод → "90m" → "1 ч 30 мин"
# ➕ → "1h" → ❌ alert «Такой интервал уже есть»
# 🗑 1 д → удалён
# 6-й интервал → ❌ alert «уже максимум»
```

## Что не сделано / вынесено

1. **Real-time планировщик отправки** (APScheduler tick → `bot.send_message`) — TASK-017.
2. **`InvalidReminderOffsetsError.reason`** структурно (Literal-поле) вместо подстрочного match — fragile. Если в TASK-015-review решим — отдельный refactor.
3. **`humanize_minutes`-тесты изолированно** не выделил — покрывается косвенно через handler-тесты (`1 ч 30 мин`, `1 д`, `1 ч` встречаются в ассертах).

## Открытые вопросы для проектировщика

1. **`_format_error` через `str(exc)` match** по подстроке — fragile. Согласуем рефакторинг `InvalidReminderOffsetsError` с `reason: Literal[...]` отдельной задачей?
2. **При `enabled=False` add/remove скрыты** — design choice. Если хочется править интервалы в выключенном виде — UI станет шумнее. Согласуем?
3. **`on_custom_offset_input` keeps state** при parser-fail и `InvalidReminderOffsetsError` — пользователь застрянет в FSM, пока не введёт валидный или не пошлёт `/reminders` (которая `state.clear`). Альтернатива — `state.clear()` при первой ошибке. Какой UX?
4. **Дубликат TASK-014 в inbox** удалил в этой же ветке (combined chore + feature). Если политика — отдельный PR для handoff-cleanup, переделаю. Сейчас слил в один — экономия PR.
5. **`MAX_OFFSET_MINUTES = 10080`** в parser-модуле, не в `ReminderService`. Если бизнес-правило «не дольше недели» должно жить в домене — переносим. Сейчас UX-ограничение парсера.
6. **Отдельный CC instance сделал TASK-014 параллельно** — handoff-протокол сработал криво (cowork положил уже-сделанную задачу в inbox). Стоит ли cowork-агенту проверять `handoff/archive/` перед публикацией задачи?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-015: «🔔 Напоминания» в боте — toggle, 6 пресетов, своё значение через FSM `EditingReminders(adding_offset)`, парсер `15m/1h/2d/N`, удаление, лимиты 5/мин-5/макс-10080. 7 handler'ов + 2 helper'а в `reminders.py`. 20 новых тестов (8 parser + 12 handler). PR [#40](https://github.com/nmetluk/bettgbot/pull/40) → squash `96f66e1`. Pre-task cleanup [#39](https://github.com/nmetluk/bettgbot/pull/39). Удалён дубликат TASK-014 из inbox.
```

## Метрики

- Файлов добавлено: 4 (parser + 2 теста + handoff)
- Файлов изменено: 5 (states, callbacks, keyboards, texts, reminders router)
- Тестов добавлено: 20 (всего теперь 146 unit + 4 migrations + 36 repos + 35 services = 221)
- Время на выполнение: ~70 мин (включая cleanup PR, разбор parallel-CC дубликата, итерации с ruff)
