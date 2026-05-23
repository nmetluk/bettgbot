---
task: TASK-013
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/35
branch: feature/TASK-013-prediction-flow
commits:
  - c796b0e feat(bot): @require_active_user decorator
  - ac88be1 feat(bot): MakingPrediction FSM states
  - 4ee4b7c feat(bot): prediction callback data
  - 3e47198 feat(bot): predict keyboards + event_card_kbd predict button
  - 3bd7a71 feat(texts): prediction UI constants
  - ba78301 refactor(bot): events router on @require_active_user + render_event_card
  - cf68f3b feat(bot): prediction router — FSM + fallback handlers
  - 2b3d388 test(bot): require_active_user decorator (6 тестов)
  - 566e24e test(bot): events fix + prediction handler tests
  - dbd760f chore(handoff): mark TASK-013 in-progress
---

# Отчёт по TASK-013: FSM «Сделать прогноз» — выбор исхода, подтверждение, upsert

## Сводка

Пользователь из карточки активного события жмёт «🎯 Сделать прогноз» / «✏️ Изменить прогноз» → видит inline-список исходов → выбирает → видит «Вы выбрали: «X». Изменить можно до DD.MM HH:MM» → подтверждает → бот пишет «✅ Прогноз сохранён» / «✏️ Прогноз обновлён». Запись идёт через готовый `PredictionService.make_prediction` (upsert) — все доменные проверки `EventNotPredictableError` / `PredictionDeadlinePassedError` / `OutcomeNotForEventError` ловятся в handler'е и превращаются в alert'ы. FSM-состояние `MakingPrediction(choosing_outcome → confirming)` хранится в Redis; `state.clear()` гарантирован в `finally` confirm и в начале cancel.

Заодно отрефакторил TASK-012-открытый вопрос #3: `_check_access(user)` inline-helper вынесен в декоратор `@require_active_user` (`src/bot/auth.py`). Все 4 callback handler'а в `events.py` переписаны на декоратор — стали короче на 3-4 строки каждый. Декоратор отличает `Message` от `CallbackQuery` через isinstance и отвечает обычным answer'ом или alert'ом соответственно.

`event_card_kbd` стала «умнее»: принимает `event_id`, `can_predict`, `has_prediction` и показывает кнопку прогноза только когда `can_predict=True` (опубликовано, не архивно, дедлайн не прошёл). Заголовок кнопки — «🎯 Сделать прогноз» или «✏️ Изменить прогноз» в зависимости от `has_prediction`. Карточка вынесена в helper `render_event_card` в `events.py` и переиспользуется в `on_predict_cancel`.

Fallback handlers `on_predict_pick_no_state` / `on_predict_confirm_no_state` — без state-фильтра, ловят callbacks из старых сообщений (после рестарта бота / истечения FSM). Отвечают alert «Событие больше недоступно». Регистрируются ПОСЛЕ stateful-версий — aiogram сначала пробует первого.

Pre-task cleanup PR [#34](https://github.com/nmetluk/bettgbot/pull/34) свернул правки cowork (CLAUDE.md «Push обязателен», handoff/README.md про Drive-зеркало, 4 DECISIONS).

## Изменённые файлы

```
+ src/bot/auth.py                                  # @require_active_user
* src/bot/states.py                                # MakingPrediction
* src/bot/callbacks.py                             # +4 callback classes
* src/bot/keyboards/__init__.py                    # +2 фабрики, изменён event_card_kbd
* src/bot/texts.py                                 # +7 констант
* src/bot/routers/events.py                        # рефакторинг на декоратор + render_event_card
* src/bot/routers/prediction.py                    # cmd_predict + 5 callback handler'ов + fallback
+ tests/unit/bot/test_auth.py                      # 6 тестов
+ tests/unit/bot/routers/test_prediction_handler.py # 16 тестов
* tests/unit/bot/routers/test_events_handler.py    # _mock_query(spec=CallbackQuery)
* handoff/inbox/TASK-013-prediction-flow.md → in-progress → archive
+ handoff/archive/TASK-013-prediction-flow/task.md
+ handoff/outbox/TASK-013-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    101 files already formatted
mypy src/shared src/bot          Success: no issues found in 54 source files
pytest                           170 passed in 10.27s

CI PR #35 — все четыре job'а зелёные:
  Lint (ruff)                     9s
  Typecheck (mypy)                18s
  Tests (pytest, unit)            22s
  Integration (alembic on real postgres)  42s
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
# /start → /events → категория → событие → 🎯 Сделать прогноз →
# исход → ✅ Подтвердить → сохранено. Повторно: ✏️ Изменить прогноз →
# другой исход → подтвердить. Отмена: ❌ Отмена → вернётся на карточку.
```

## Что не сделано / вынесено

1. **Прямой entry-point** «🎯 Сделать прогноз» с пропуском карточки события — отдельная TASK-013a при необходимости.
2. **Pagination в выборе исходов** — у событий обычно 2-3 исхода, пагинация избыточна.
3. **Integration-тесты handler'ов с aiogram-runtime** — DoD запрещает; mock-based достаточны.
4. **`@require_active_user` сужение типа `user`** — mypy не понимает, что после декоратора user не None. В handler'е остаётся `User | None`, но handler не проверяет — есть `assert user is not None` где это нужно для mypy.

## Открытые вопросы для проектировщика

1. **`assert user is not None`** в handler'ах после `@require_active_user`. Альтернативы: `cast(User, user)`, явный параметр `User` (но тип в декораторе и handler разные → путаница). Текущий выбор (assert) даёт runtime-safety. OK?
2. **Fallback handlers без state-фильтра** для `PredictPickCb` / `PredictConfirmCb` отвечают alert «Событие больше недоступно». Альтернатива — edit_text + кнопка «Открыть событие заново». Сейчас минимум — пользователь видит alert и сам жмёт «📅 Все события». OK?
3. **`render_event_card` в `events.py` импортируется в `prediction.py`** через локальный импорт (избежание цикла). Если станет шумно — вынесу в `src/bot/_event_card.py`. Сейчас один локальный импорт.
4. **`on_predict_cancel` без state-фильтра** ловит PredictCancelCb из любого state (включая no-state). Это правильно (отмена — глобальное действие), но не консистентно с stateful start/pick/confirm. Согласуем как явный design choice?
5. **`@require_active_user` + последующий вызов другого декорированного handler'а** (`cmd_predict` → `cmd_events`) — декоратор сработает дважды. Дополнительный SQL-запрос для проверки user (нет — user уже в data). Реально просто 2 if'а, накладной расход незаметный. Если важно — `cmd_predict` может звать `cmd_events.__wrapped__`. Сейчас не оптимизировал.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-013: FSM «Сделать прогноз» — `MakingPrediction(choosing_outcome → confirming)` в Redis, 5 callback handler'ов (start/pick/confirm/cancel/fallback). Кнопка прогноза в карточке события (when can_predict). Рефакторинг `_check_access` → `@require_active_user` декоратор; `events.py` стал короче на ~25 строк. `render_event_card` helper для переиспользования. 22 новых unit-теста. PR [#35](https://github.com/nmetluk/bettgbot/pull/35) → squash `e7ee4f2`. Pre-task cleanup [#34](https://github.com/nmetluk/bettgbot/pull/34).
```

## Метрики

- Файлов добавлено: 3 (auth, 2 тестовых модуля)
- Файлов изменено: 7 (states, callbacks, keyboards, texts, events router, prediction router, events test)
- Тестов добавлено: 22 (всего теперь 170: 95 unit + 4 migrations + 36 repos + 35 services)
- Время на выполнение: ~70 мин (включая cleanup PR, фикс `_mock_query(spec=CallbackQuery)` регрессии тестов TASK-012, итерации с ruff RUF059)
