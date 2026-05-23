---
id: TASK-010
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/01-architecture.md
  - docs/02-tech-stack.md
  - docs/04-bot-flows.md
  - docs/08-conventions.md
priority: high
estimate: L
---

# TASK-010: aiogram bootstrap — dispatcher, middleware, скелет роутеров

## Контекст

После TASK-009 у нас полностью готов доменный слой. Теперь стартует TG-бот: bootstrap-приложение, единая точка входа, dispatcher с RedisStorage для FSM, middleware (логирование + БД-сессия + поиск/touch пользователя), пустые скелеты роутеров на каждую команду. Реальные handler'ы (`/start`, `/events`, `/predict`, `/my`, `/reminders`, `/help`) идут позже отдельными задачами TASK-011 — TASK-016.

Это первая задача, которая трогает `src/bot/`. Структура — из [docs/08-conventions.md](../../docs/08-conventions.md) («Структура `src/`»). Сценарии — [docs/04-bot-flows.md](../../docs/04-bot-flows.md). Архитектурный поток — [docs/01-architecture.md](../../docs/01-architecture.md).

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: дописана секция «Импорты: side-effects в пакетных `__init__.py`» и правило #3 в `docs/08-conventions.md`, обновлённые `state/PROJECT_STATUS.md` и `state/DECISIONS.md` (5 новых записей), новая сессия `sessions/2026-05-23-08-task-009-review/`. Упакуй в `chore/post-TASK-009-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-010-bot-bootstrap` от свежего `main`.

## Цель

`python -m src.bot.main` поднимает aiogram-бота: подключается к Telegram через long-polling, через middleware на каждом update открывает `AsyncSession`, инжектирует её и (если есть) `User` в `data`, логирует update с структурным `request_id`/`tg_user_id`/`latency_ms`. Routers зарегистрированы (пустые), `make` ничего нового нет (bot запускается через Docker позже в TASK-027 или через `uv run python -m src.bot.main` локально). RedisStorage для FSM настроен. Тесты middleware и smoke-тест на сборку dispatcher'а — зелёные.

## Definition of Done

### Step 0 — Tweaks из TASK-009 review (один коммит до bot-кода)

- [ ] **`src/shared/services/event.py`**: в `delete_outcome` убрать `await self._session.rollback()`. После — `try: delete + audit + commit; except IntegrityError: raise OutcomeInUseError(...)`. Тест `test_delete_outcome_in_use_raises` должен остаться зелёным.
- [ ] **`tests/integration/conftest.py`**: дописать docstring модуля и/или короткий комментарий к фикстуре `session` про разделение «когда `session`, когда `nested_session`». Пример:
  ```python
  """Общий conftest для integration-тестов.

  Две session-фикстуры:
  - `session` (здесь) — простой rollback в финале; для repository-тестов,
    которые **не вызывают** `session.commit()`.
  - `nested_session` (в `tests/integration/services/conftest.py`) — внешняя
    транзакция + SAVEPOINT для тестов сервисов, которые `commit()` внутри;
    SAVEPOINT откатывается, поэтому коммит не персистится.
  """
  ```
- [ ] **Один Conventional-коммит**: `refactor(services): drop rollback in delete_outcome; clarify session fixtures`.

### Step 1 — `src/bot/main.py` (entrypoint)

- [ ] Module docstring + `__all__` (можно пустой).
- [ ] `async def main() -> None`:
  - `configure_logging(settings.log_level, settings.log_format)` — единый структурный лог.
  - `bot = Bot(token=settings.telegram_bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))`.
  - `storage = RedisStorage.from_url(str(settings.redis_url))` — FSM в Redis (см. [docs/02-tech-stack.md](../../docs/02-tech-stack.md)).
  - `dp = Dispatcher(storage=storage)`.
  - Подключить middleware-ы: `dp.update.middleware(LoggingMiddleware())`, `dp.update.middleware(SessionMiddleware())`, `dp.update.middleware(UserMiddleware())`.
  - Импортировать routers (`from src.bot.routers import all_routers`) и `dp.include_routers(*all_routers)`.
  - `await bot.delete_webhook(drop_pending_updates=True)`.
  - `await dp.start_polling(bot)`.
  - В `finally`: `await bot.session.close()`, `await storage.close()` (или просто `dispose engine` — на твой выбор; engine может пережить bot, dispose делать в shutdown).
- [ ] `if __name__ == "__main__":` → `asyncio.run(main())` с перехватом `KeyboardInterrupt`/`SystemExit` для чистого выхода (логировать «shutdown»).
- [ ] Использовать `from src.shared.config import settings` и `from src.shared.logging import configure_logging, get_logger`. Logger биндится на module-level: `logger = get_logger(__name__)`.

### Step 2 — Middleware

`src/bot/middlewares/__init__.py`:

- [ ] Re-export `LoggingMiddleware`, `SessionMiddleware`, `UserMiddleware`, `__all__`.

`src/bot/middlewares/logging.py`:

- [ ] `class LoggingMiddleware(BaseMiddleware)` — на каждом update:
  - Сгенерировать `request_id = uuid.uuid4().hex[:12]`.
  - Из update попытаться вытащить `update_id`, `tg_user_id` (опционально, не всегда есть в апдейтах типа `my_chat_member`).
  - Через `structlog.contextvars.bind_contextvars(request_id=..., update_id=..., tg_user_id=...)` забиндить в контекст-логгер.
  - `t0 = time.monotonic()`, вызвать `handler(event, data)`, в `finally` залогировать `bot.update.handled` с `latency_ms=int((time.monotonic() - t0) * 1000)`, `handler=<resolved by aiogram, опционально>`, `outcome=<ok|exception>`.
  - `structlog.contextvars.clear_contextvars()` в финале (чтобы не утекать в следующий update).
  - Исключения — пробрасывать, не глотать; залогировать `bot.update.failed` с `exception_type=type(exc).__name__`.

`src/bot/middlewares/session.py`:

- [ ] `class SessionMiddleware(BaseMiddleware)`:
  - `async with SessionLocal() as session: data["session"] = session; result = await handler(event, data)`.
  - Никаких commit'ов — это делают сервисы внутри handler'ов.
  - При исключении контекст-менеджер `AsyncSession` сам сделает rollback.

`src/bot/middlewares/user.py`:

- [ ] `class UserMiddleware(BaseMiddleware)`:
  - Извлечь `tg_user_id` из `event.from_user.id` (через aiogram-помощник `event.from_user`, если есть; для системных апдейтов — None, тогда сразу к handler'у).
  - `session: AsyncSession = data["session"]` (берём из data, который положил `SessionMiddleware`).
  - `user_repo = UserRepository(session)`.
  - `user = await user_repo.get_by_tg_user_id(tg_user_id)`.
  - `data["user"] = user` (может быть `None` — handler сам решит, что делать; в TASK-011 `/start` будет ловить case «user is None и это не /start» и редиректить).
  - Если `user is not None`: `await UserService(session, registry=...).touch_last_seen(user.id)` — **подумай**: `UserService` нужен `registry`, чтобы конструктор пропустил, но `touch_last_seen` registry не использует. Варианты:
    - (а) Сделать `UserService.__init__(session, registry=None)` — registry optional. Тогда middleware может вызывать без registry.
    - (б) Использовать `UserRepository.touch_last_seen` напрямую + `await session.commit()` в middleware (это нарушает «commit в сервисе», но `touch_last_seen` — тонкая операция).
    - (в) Сделать отдельный `UserActivityService` без registry-зависимости.

    Выбери **(а)** — самое простое и без нарушения слоёв. Поправь `UserService.__init__` соответственно: `def __init__(self, session, registry: ExternalUserRegistryClient | None = None)`. Методы, которым registry **нужен** (`register_or_authenticate`), при `registry is None` поднимают `RuntimeError("registry is required for registration")` — это страховка, чтобы случайно не упустить.

### Step 3 — Routers (пустые скелеты)

`src/bot/routers/__init__.py`:

- [ ] Импортирует и экспортирует `all_routers: list[Router]` — список из шести роутеров в порядке регистрации.

`src/bot/routers/start.py`, `events.py`, `prediction.py`, `my.py`, `reminders.py`, `help.py`:

- [ ] Каждый — `router = Router(name="<name>")`. Никаких handler'ов. Module docstring «реальные handler'ы — в TASK-NNN». Пустой `__all__ = ["router"]`.

### Step 4 — Keyboards, States, Texts (минимум)

`src/bot/keyboards/__init__.py`:

- [ ] `def main_menu() -> ReplyKeyboardMarkup` — постоянная клавиатура из [docs/04-bot-flows.md](../../docs/04-bot-flows.md):
  ```
  [📅 Все события]   [🎯 Сделать прогноз]
  [📋 Мои прогнозы]  [🔔 Напоминания]
  [ℹ️ Справка]
  ```
  `resize_keyboard=True`. Без обработчиков — просто фабрика клавиатуры.
- [ ] `def contact_request() -> ReplyKeyboardMarkup` — одна кнопка `request_contact=True` с текстом «📱 Поделиться контактом» (для TASK-011, но фабрика тут).
- [ ] Module docstring + `__all__`.

`src/bot/states.py`:

- [ ] Пустой модуль с docstring «FSM-states будут добавлены вместе с handler'ами (TASK-013, TASK-015)».
- [ ] Импорт `StatesGroup` из `aiogram.fsm.state` для совместимости готов; FSM-классы добавятся в реальных задачах.

`src/bot/texts.py`:

- [ ] Module docstring «Все тексты UI бота. Конвенция — UPPER_SNAKE_CASE константы, без хардкода в handler'ах».
- [ ] Минимум:
  - `WELCOME_NEW = "👋 Привет! ..."` (из bot-flows)
  - `WELCOME_RETURNING = "С возвращением!"`
  - `NEED_CONTACT = "Чтобы пользоваться ботом, поделитесь, пожалуйста, контактом..."`
  - `PHONE_NOT_FOUND = "Ваш номер не найден в реестре. Обратитесь к администратору."`
  - `REGISTRY_UNAVAILABLE = "Не удалось проверить номер прямо сейчас. Попробуйте позже."`
  - `HELP = "ℹ️ Справка ..."` (полный текст из bot-flows)
  - `ACCESS_DENIED = "Ваш доступ ограничен. Обратитесь к администратору."` (для is_blocked)
  - `NEED_START = "Сначала зарегистрируйтесь: /start"` (для запросов от незарегистрированных)
- [ ] `__all__` с явным списком — чтобы было видно, какие тексты есть.

### Step 5 — `src/bot/__init__.py`

- [ ] Module docstring; пустой `__all__` (внешний мир импортирует через подмодули `src.bot.main` и т.п.).

### Step 6 — Тесты

`tests/unit/bot/`:

- [ ] `tests/unit/bot/__init__.py` (пустой).
- [ ] `tests/unit/bot/test_main_smoke.py`:
  - `test_dispatcher_constructs` — импортирует `src.bot.main`, конструирует `Bot` + `Dispatcher` (без `start_polling`), проверяет, что 6 routers зарегистрированы и три middleware'а привязаны.
  - Это **smoke** — гарантия, что `python -m src.bot.main` хотя бы не упадёт на bootstrap'е.
- [ ] `tests/unit/bot/test_middlewares_logging.py`:
  - `test_logging_middleware_binds_contextvars` — мокаем `bind_contextvars`/`clear_contextvars`, вызываем middleware с фейковым update'ом, проверяем bind/clear порядок.
  - `test_logging_middleware_logs_latency` — capsys, проверяем что лог `bot.update.handled` пишется и содержит `latency_ms`.
  - `test_logging_middleware_logs_exception` — handler бросает, проверяем `bot.update.failed`, исключение пробрасывается.
- [ ] `tests/unit/bot/test_middlewares_session.py`:
  - `test_session_middleware_injects_session` — мокаем `SessionLocal` через `monkeypatch.setattr` на `src.shared.db.SessionLocal`, проверяем, что `data["session"]` появляется в handler-вызове.
  - `test_session_middleware_closes_on_exception` — handler бросает, проверяем, что `__aexit__` сессии вызван (через мок).
- [ ] `tests/unit/bot/test_middlewares_user.py`:
  - `test_user_middleware_injects_user_when_exists` — заранее в БД создан user (через integration session); middleware кладёт в data. **Это integration-уровень** — переноси в `tests/integration/bot/` и помечай маркером.
  - `test_user_middleware_injects_none_when_absent` — то же, но user не существует.
  - `test_user_middleware_touches_last_seen` — проверка вызова `touch_last_seen`.

  Если интеграционные тесты на middleware превращаются в большой кусок инфраструктуры, ограничься mock-тестами в `tests/unit/bot/test_middlewares_user.py` — мокаем `UserRepository.get_by_tg_user_id` и `UserService.touch_last_seen`. На MVP этого достаточно.

### Step 7 — Подправить `UserService` (если выбрал вариант (а))

- [ ] **`src/shared/services/user.py`**: `def __init__(self, session: AsyncSession, registry: ExternalUserRegistryClient | None = None) -> None:`. `register_or_authenticate` в начале: `if self._registry is None: raise RuntimeError("registry is required for register_or_authenticate")`.
- [ ] Обновить existing `test_user_service.py`: сценарии, не использующие registry (`touch_last_seen`, `block/unblock`), могут опустить `registry=...`. `register_or_authenticate` — оставлять с registry.
- [ ] Добавить тест `test_register_without_registry_raises_runtimeerror`.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный (strict). mypy для bot — без strict, как было решено в `docs/08-conventions.md`.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая новые bot-тесты.
- [ ] `uv run pytest tests/integration -m integration` — без падений (новые integration-тесты опциональны).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка локально (опционально, не в DoD):** `make up`, `make migrate`, `TELEGRAM_BOT_TOKEN=<реальный токен>` в `.env`, `uv run python -m src.bot.main` → бот запускается, отвечает в TG любым update'ом без ошибок (handler'ов нет, поэтому ответа не будет — но и crash'а тоже).
- [ ] Ветка `feature/TASK-010-bot-bootstrap`, Conventional Commits (минимум):
  - `refactor(services): drop rollback in delete_outcome; clarify session fixtures` (Step 0)
  - `feat(bot): main entrypoint with dispatcher and redis fsm`
  - `feat(bot): logging, session, user middlewares`
  - `feat(bot): empty router stubs, keyboards, texts`
  - `refactor(services): make UserService.registry optional`
  - `test(bot): smoke + middleware tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-010-report.md`, задача → `handoff/archive/TASK-010-bot-bootstrap/task.md`.

## Артефакты

```
* src/shared/services/event.py            # Step 0: drop rollback
* src/shared/services/user.py             # registry Optional
* tests/integration/conftest.py            # Step 0: docstring/comment
* tests/integration/services/test_user_service.py  # без registry для не-register тестов
+ src/bot/__init__.py
+ src/bot/main.py
+ src/bot/middlewares/__init__.py
+ src/bot/middlewares/logging.py
+ src/bot/middlewares/session.py
+ src/bot/middlewares/user.py
+ src/bot/routers/__init__.py             # all_routers list
+ src/bot/routers/start.py
+ src/bot/routers/events.py
+ src/bot/routers/prediction.py
+ src/bot/routers/my.py
+ src/bot/routers/reminders.py
+ src/bot/routers/help.py
+ src/bot/keyboards/__init__.py
+ src/bot/states.py
+ src/bot/texts.py
- src/bot/.gitkeep
+ tests/unit/bot/__init__.py
+ tests/unit/bot/test_main_smoke.py
+ tests/unit/bot/test_middlewares_logging.py
+ tests/unit/bot/test_middlewares_session.py
+ tests/unit/bot/test_middlewares_user.py
```

## Ссылки

- [docs/01-architecture.md](../../docs/01-architecture.md) — handler → service → repo, sequence-диаграммы
- [docs/02-tech-stack.md](../../docs/02-tech-stack.md) — Redis для FSM, aiogram 3.x, structlog
- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — главное меню, тексты, логирование с `request_id`/`update_id`/`user_id`/`latency_ms`
- [docs/08-conventions.md](../../docs/08-conventions.md) — `src/bot/` структура, `logger = get_logger(__name__)`, тексты в `texts.py`

## Подсказки исполнителю

- **aiogram 3.x:**
  - `from aiogram import Bot, Dispatcher, Router`
  - `from aiogram.client.default import DefaultBotProperties`
  - `from aiogram.enums import ParseMode`
  - `from aiogram.fsm.storage.redis import RedisStorage`
  - `from aiogram import BaseMiddleware`
- **RedisStorage** — лениво подключается; создание не требует, чтобы Redis был up. Это удобно для тестов: `RedisStorage.from_url("redis://localhost:6379/0")` не упадёт при collection.
- **`dp.update.middleware(...)`** регистрирует на всех update-types; есть и более узкие — `dp.message.middleware(...)` и т.п. Для общих middleware (логирование, сессия) — `update.middleware` правильно.
- **Извлечение `from_user`** — у `Message`, `CallbackQuery`, `InlineQuery` есть `.from_user`. У `Update` напрямую — `update.message and update.message.from_user`. Удобный хелпер: `aiogram.types.User`. Если апдейт не содержит пользователя (например, `my_chat_member` без `from`) — `data["user"] = None`, и handler сам разбирается.
- **`tests/unit/bot/test_main_smoke.py`** — не запускай polling. Конструкция через:
  ```python
  from src.bot.main import build_dispatcher  # вынеси сборку Dispatcher в отдельную функцию
  bot, dp = build_dispatcher()
  assert len(dp.sub_routers) == 6
  ```
  Это позволит тестам smoke-проверять конфигурацию без рантайма.
- **Middleware-тесты** — aiogram 3 даёт чистый интерфейс: `BaseMiddleware.__call__(self, handler, event, data)`. Тесты вызывают middleware напрямую с `handler=AsyncMock()` и каким-то простым `event`.
- **Импорты из `src.shared.external.registry`** для типа `ExternalUserRegistryClient` — следуй правилу из [docs/08-conventions.md](../../docs/08-conventions.md) (новая секция «Импорты: side-effects в пакетных `__init__.py`»).
- **Token из Settings** — `settings.telegram_bot_token.get_secret_value()`. Не логируй сырое значение.
- **`build_dispatcher()` фабрика** — сделай чистую (testable) сборку отдельно от `main()`-loop. Это упростит smoke-тест и future scheduler integration.

## Что НЕ делать

- Не писать реальные handler'ы — это TASK-011 — TASK-016. Routers — **пустые скелеты**.
- Не подключать APScheduler (фоновые задачи) — это TASK-017/TASK-018.
- Не подключать webhook — на старте только long-polling.
- Не запускать `start_polling` в тестах.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` (кроме Step 0, который трогает `tests/integration/conftest.py` — это код, не doc).
- Не добавлять зависимости (`aiogram[redis]`, `redis` уже в `pyproject.toml`).
