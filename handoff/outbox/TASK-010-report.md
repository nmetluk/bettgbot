---
task: TASK-010
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/26
branch: feature/TASK-010-bot-bootstrap
commits:
  - b711301 refactor(services): drop rollback in delete_outcome; clarify session fixtures
  - 8d3da6b feat(bot): main entrypoint with dispatcher and redis fsm
  - 754892b feat(bot): logging, session, user middlewares
  - 39dfd65 feat(bot): empty router stubs, keyboards, texts
  - 66b5b01 refactor(services): make UserService.registry optional
  - 362eb71 test(bot): smoke + middleware tests + register-without-registry
---

# Отчёт по TASK-010: aiogram bootstrap — dispatcher, middleware, скелет роутеров

## Сводка

Бот завёлся: `python -m src.bot.main` поднимает aiogram-приложение с RedisStorage FSM, тремя middleware'ами (logging, session, user) и шестью пустыми роутерами в порядке `start → events → prediction → my → reminders → help`. Реальные handler'ы — TASK-011 — TASK-016.

`LoggingMiddleware` биндит `request_id`/`update_id`/`tg_user_id` через `structlog.contextvars` на время handler'а; пишет `bot.update.handled` с `latency_ms` (или `bot.update.failed` с `exception_type` при исключении), очищает contextvars в `finally`. Извлечение `from_user` устойчиво: проверяет напрямую и вложенные `message/callback_query/inline_query/edited_message`.

`SessionMiddleware` открывает `AsyncSession` через `SessionLocal()` и кладёт в `data["session"]`. Commit/rollback — задача сервисов; контекст-менеджер сессии закроется автоматически (включая исключения).

`UserMiddleware` ищет `User` по `tg_user_id`, кладёт в `data["user"]` (может быть `None`). Если пользователь есть — вызывает `UserService(session).touch_last_seen(user.id)`. **`UserService.registry` стал Optional**: для `touch_last_seen`/`block`/`unblock`/read registry не нужен, а `register_or_authenticate` явно поднимает `RuntimeError("registry is required ...")` при попытке вызвать без registry.

`build_dispatcher()` выделена из `main()` ради testability — конструирует `Bot+Dispatcher` без `start_polling`, использует `get_settings()` (не module-level `settings`), чтобы тест мог monkeypatch'ить токен. `main()` делает `configure_logging` → `delete_webhook(drop_pending_updates=True)` → `start_polling`, `bot.session.close()` в `finally`. CLI-обвязка через `contextlib.suppress(KeyboardInterrupt, SystemExit)` — чистый выход.

Создан `src/__init__.py` — без него mypy жалуется `Source file found twice under different module names: "shared.logging" and "src.shared.logging"`, потому что bot.main.py использует absolute import `from src.shared.logging`, а shared/__init__.py — relative `from .logging`. С `src` как полноценным пакетом оба пути дают одно каноническое имя `src.shared.logging`. Альтернатива (mypy_path + explicit_package_bases) сложнее.

Step 0 свернул два TASK-009 review-tweaks одним коммитом: убран лишний `rollback` после IntegrityError в `EventService.delete_outcome` (caller-контекст откатит сам); добавлен docstring в `tests/integration/conftest.py` про разделение `session` vs `nested_session`.

Pre-task cleanup PR [#25](https://github.com/nmetluk/bettgbot/pull/25) свёл правки cowork (новая секция «Импорты: side-effects в пакетных __init__.py» в `docs/08-conventions.md`, 5 DECISIONS, sessions/2026-05-23-08).

## Изменённые файлы

```
* src/shared/services/event.py             # drop rollback
* src/shared/services/user.py              # registry Optional + raises
+ src/__init__.py                          # пакет, не namespace — для mypy
+ src/bot/main.py                          # build_dispatcher + main + cli
+ src/bot/middlewares/__init__.py
+ src/bot/middlewares/logging.py
+ src/bot/middlewares/session.py
+ src/bot/middlewares/user.py
+ src/bot/routers/__init__.py              # all_routers list
+ src/bot/routers/start.py / events.py / prediction.py / my.py / reminders.py / help.py
+ src/bot/keyboards/__init__.py            # main_menu + contact_request
+ src/bot/states.py                        # заготовка
+ src/bot/texts.py                         # 8 UI-констант
* src/bot/__init__.py                      # docstring
* src/migrations/env.py                    # ruff format
+ tests/unit/bot/__init__.py
+ tests/unit/bot/test_main_smoke.py        # 1
+ tests/unit/bot/test_middlewares_logging.py    # 3
+ tests/unit/bot/test_middlewares_session.py    # 2
+ tests/unit/bot/test_middlewares_user.py       # 3
* tests/integration/conftest.py            # docstring session vs nested_session
* tests/integration/services/test_user_service.py    # +1 без registry
* tests/unit/conftest.py                   # TELEGRAM_BOT_TOKEN = '111111:stub-token'
* handoff/inbox/TASK-010-bot-bootstrap.md → in-progress → archive
+ handoff/archive/TASK-010-bot-bootstrap/task.md
+ handoff/outbox/TASK-010-report.md
```

## Тесты и CI

```
ruff check src tests              All checks passed!
ruff format --check src tests     92 files already formatted
mypy src/shared src/bot (strict)  Success: no issues found in 51 source files
pytest                            119 passed in 8.78s
  - 50 unit (config/logging/smoke + external + bot)
  - 4 migrations
  - 33 repositories
  - 32 services (включая +1 register-без-registry)

CI PR #26 — все четыре job'а зелёные:
  Lint (ruff)                     9s
  Typecheck (mypy)                17s
  Tests (pytest, unit)            15s
  Integration (alembic on real postgres)  43s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env       # настрой TELEGRAM_BOT_TOKEN на реальный
make up && make migrate

uv run pytest -m "not integration" -v   # 50
uv run pytest tests/integration -m integration -v  # 69

# Ручной запуск бота (handler'ов ещё нет, но bootstrap должен пройти без crash'а):
uv run python -m src.bot.main
```

## Что не сделано / вынесено

1. **Handler'ы команд** — TASK-011 — TASK-016 (по одной задаче на команду).
2. **APScheduler** — TASK-017/018.
3. **Webhook** — поставка только long-polling на старте.
4. **Integration-тесты UserMiddleware** через реальный БД — оставил mock-уровень (DoD это явно допускает).
5. **Smoke-тест на handlers** — не нужен сейчас, появится с TASK-011.

## Открытые вопросы для проектировщика

1. **`src/__init__.py` создан.** Это меняет соглашение «src — namespace package» на «src — обычный пакет». Альтернатива — `mypy_path = "src"` + `explicit_package_bases = true`. Текущее проще и меньше магии. Фиксируем в `docs/08-conventions.md`?
2. **`UserMiddleware.touch_last_seen` — 2 round-trip'а** (SELECT user + UPDATE last_seen + commit) на каждый update. На MVP норм; если станет узким — варианты: throttling через Redis (last_seen обновляется не чаще раза в N минут), или Redis-based кеш user → last_seen, периодически flush'ить в БД. Сейчас фиксировать как «MVP-долг»?
3. **`build_dispatcher` использует `get_settings()`** вместо module-level `settings` — паттерн «фабрики читают свежий конфиг». То же сделал в `get_registry_client` (TASK-008 review). Зафиксировать в `docs/08-conventions.md` как третье правило раздела «Импорты»?
4. **`structlog.contextvars` clear в finally** — guarantee изоляции между updates. Если позже добавим `pytest-asyncio + concurrent updates` — нужно ли усиление через task-locals? Сейчас норм, contextvars per-task.
5. **`tests/unit/conftest.py: TELEGRAM_BOT_TOKEN = "111111:stub-token"`** — валидный для aiogram, чтобы smoke не падал. Если CI workflow `env:` для unit job появится с другим значением — `monkeypatch.setenv` в smoke-тесте всё равно перетрёт. Текущее устойчивое; согласуем как «test-fixture стабильно валидна».

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-010: aiogram bootstrap — `src/bot/main.py` с `build_dispatcher()` (testable), `RedisStorage` для FSM, три middleware (`LoggingMiddleware` с structlog.contextvars + latency, `SessionMiddleware`, `UserMiddleware`), 6 пустых роутеров, фабрики клавиатур, UI-тексты. TASK-009 tweaks (drop rollback в `delete_outcome`, conftest docstring). `UserService.registry` стал Optional. 9 новых unit-тестов (smoke + 3 middleware × 2-3). PR [#26](https://github.com/nmetluk/bettgbot/pull/26) → squash `5224140`. Pre-task cleanup [#25](https://github.com/nmetluk/bettgbot/pull/25).
```

## Метрики

- Файлов добавлено: 22 (15 в `src/bot/` + 5 тестов + `src/__init__.py` + handoff)
- Файлов изменено: 7 (event/user сервисы, src/migrations/env, conftest, test_user_service, tests/unit/conftest, src/bot/__init__)
- Тестов добавлено: 9 (всего теперь 119: 50 unit + 4 migrations + 33 repos + 32 services)
- Время на выполнение: ~80 мин (включая cleanup PR, итерации с mypy/ruff/aiogram-token, фикс конфликта shared.* vs src.shared.* через src/__init__.py)
