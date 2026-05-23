---
id: TASK-011
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/06-external-api.md
  - docs/08-conventions.md
  - src/bot/texts.py
  - src/bot/keyboards/__init__.py
priority: high
estimate: M
---

# TASK-011: `/start` + Contact handler — регистрация пользователя

## Контекст

Первый реальный handler. После TASK-010 у нас bootstrap (dispatcher, middleware, пустые routers), но ни один update пока не обрабатывается. Эта задача заполняет `src/bot/routers/start.py` двумя handler'ами: `/start` (для новых и существующих пользователей) и `Message(F.contact)` (приём контакта при регистрации). Это последний шаг к рабочему циклу «новый пользователь шлёт /start → делится контактом → проверка во внешнем реестре → создаётся `User` → главное меню».

Источники:

- [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) — раздел «Регистрация (`/start`)», точные тексты и edge-cases (свой/чужой контакт, registry not_found, ExternalApiError).
- [`docs/06-external-api.md`](../../docs/06-external-api.md) — контракт `ExternalUserRegistryClient`.
- [`docs/08-conventions.md`](../../docs/08-conventions.md) — стиль логов, импорты внешних модулей, фабрики через `get_settings()`.
- [`src/bot/texts.py`](../../src/bot/texts.py) — все UI-тексты уже есть (`WELCOME_NEW`, `WELCOME_RETURNING`, `NEED_CONTACT`, `PHONE_NOT_FOUND`, `REGISTRY_UNAVAILABLE`, `ACCESS_DENIED`, `NEED_START`).
- [`src/bot/keyboards/__init__.py`](../../src/bot/keyboards/__init__.py) — `main_menu()` и `contact_request()` уже есть.

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: расширена секция «Импорты» и добавлена «Фабрики читают свежий конфиг» в `docs/08-conventions.md`, новый раздел «Технический долг» в `state/BACKLOG.md`, обновлённые `state/PROJECT_STATUS.md` и `state/DECISIONS.md` (5 новых записей), новая сессия `sessions/2026-05-23-09-task-010-review/`. Упакуй в `chore/post-TASK-010-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-011-start-handler` от свежего `main`.

## Цель

В Telegram бот реально работает первый сценарий: пользователь шлёт `/start`, бот разбирается, существует он или нет, в нужный момент просит контакт, проверяет номер через внешний реестр (mock в dev), создаёт `User` + дефолтный `ReminderSetting`, отвечает «Добро пожаловать» с главным меню. Все ветки edge-cases отрабатываются понятными текстами. DI registry — через `dp["registry"]` workflow-data, чтобы handler принимал её как параметр.

## Definition of Done

### Step 1 — DI registry через `dp["registry"]`

- [ ] **`src/bot/main.py` → `build_dispatcher()`**: после `dp = Dispatcher(storage=storage)` добавить `dp["registry"] = get_registry_client()`. Импорт: `from src.shared.external import get_registry_client` (тут пакетный импорт оправдан — фабрика реально нужна).
- [ ] **`main()` shutdown**: после `start_polling` (в `finally`) закрыть HTTP-клиент через `await dp["registry"].close()`, **но только если** у объекта есть `.close()` (mock не имеет — используй `hasattr` или `getattr(..., None)`).
- [ ] Тест в `tests/unit/bot/test_main_smoke.py`: после `build_dispatcher()` проверить `dp["registry"] is not None` и `isinstance(dp["registry"], ExternalUserRegistryClient)` (через `runtime_checkable` Protocol).

### Step 2 — handler `/start` в `src/bot/routers/start.py`

- [ ] Module docstring «Handler `/start` и приём контакта при регистрации (TASK-011)».
- [ ] `router = Router(name="start")`.
- [ ] **Handler `/start`**:
  ```python
  @router.message(CommandStart())
  async def cmd_start(
      message: Message,
      user: User | None,        # из UserMiddleware (data["user"])
      state: FSMContext,        # на всякий случай сбросим текущий FSM-state (TASK-013, TASK-015)
  ) -> None:
  ```
  - Сбросить FSM-state: `await state.clear()` (на случай, если пользователь жал `/start` в середине «Сделать прогноз»).
  - Если `user is None` (или `user.is_blocked is True`):
    - Если `user is not None and user.is_blocked`: отправить `texts.ACCESS_DENIED` без клавиатуры (`ReplyKeyboardRemove`). Return.
    - Иначе (`user is None`): отправить `texts.WELCOME_NEW` + `keyboards.contact_request()`. Return.
  - Иначе (зарегистрирован): отправить `texts.WELCOME_RETURNING` + `keyboards.main_menu()`. Логнуть `bot.start.returning_user` с `user_id`.
- [ ] **Handler Contact** (отдельная функция, тот же router):
  ```python
  @router.message(F.contact)
  async def on_contact(
      message: Message,
      session: AsyncSession,
      registry: ExternalUserRegistryClient,   # workflow-data из dp["registry"]
      user: User | None,
      state: FSMContext,
  ) -> None:
  ```
  - Если `user is not None and user.is_blocked`: `texts.ACCESS_DENIED` + `ReplyKeyboardRemove`. Return.
  - Если `message.contact.user_id != message.from_user.id`: отправить «Поделитесь, пожалуйста, **своим** контактом» (новая константа `texts.NEED_OWN_CONTACT`) + `keyboards.contact_request()`. Return.
  - Уже зарегистрирован? Если `user is not None`: «Вы уже зарегистрированы» (новая константа `texts.ALREADY_REGISTERED`) + `keyboards.main_menu()`. Return.
  - Вызвать `UserService(session, registry=registry).register_or_authenticate(...)` с полями из `message.contact` (`phone_number`, `first_name`, `last_name`) и `message.from_user.id` / `username`.
    - При успехе: «Добро пожаловать, {first_name}!» (новая константа `texts.WELCOME_NEW_REGISTERED` с `{first_name}`-плейсхолдером — добавь в texts.py) + `keyboards.main_menu()`. Залогируй `bot.start.registered` с `tg_user_id`, `phone_hash` (используй helper из http_registry или сделай локальный).
    - `UserNotAllowed` → `texts.PHONE_NOT_FOUND` + `keyboards.contact_request()` (даём ещё попробовать). Залогируй `bot.start.not_allowed` с `reason`.
    - `RegistryUnavailableError` → `texts.REGISTRY_UNAVAILABLE` + `keyboards.contact_request()`. Залогируй `bot.start.registry_unavailable`.
    - Любой другой `DomainError` → переподнять (LoggingMiddleware запишет `bot.update.failed`).
- [ ] **Дополнить `texts.py`** новыми константами:
  - `NEED_OWN_CONTACT = "Поделитесь, пожалуйста, своим контактом — нажмите кнопку ниже."`
  - `ALREADY_REGISTERED = "Вы уже зарегистрированы. Главное меню ниже."`
  - `WELCOME_NEW_REGISTERED = "Добро пожаловать, {first_name}! Главное меню ниже."` — с placeholder
  - (опц.) если `BLOCKED_REASON` нужен в `PHONE_NOT_FOUND` — параметризовать; но проще оставить общий PHONE_NOT_FOUND без причины (агенту админки виднее)
  - Обнови `__all__`.

### Step 3 — Тонкости aiogram

- [ ] **Импорты handler'а**:
  ```python
  from aiogram import F, Router
  from aiogram.filters import CommandStart
  from aiogram.fsm.context import FSMContext
  from aiogram.types import Message, ReplyKeyboardRemove
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.shared.external.registry import ExternalUserRegistryClient
  from src.shared.exceptions import RegistryUnavailableError, UserNotAllowed
  from src.shared.models import User
  from src.shared.services import UserService

  from .. import keyboards, texts
  ```
- [ ] **Тип `user: User | None`** — пробрасывается из `UserMiddleware` через `data["user"]`. aiogram автоматически инжектирует по имени параметра + аннотации.
- [ ] **Тип `registry: ExternalUserRegistryClient`** — workflow-data из `dp["registry"]`, инжектится по имени.
- [ ] **`message.from_user.id` точно есть** при `CommandStart()` и `F.contact` — в этих случаях `from_user` не None. Если mypy ругается — `assert message.from_user is not None`.

### Step 4 — Unit-тесты

`tests/unit/bot/routers/`:

- [ ] `tests/unit/bot/routers/__init__.py` (пустой).
- [ ] `tests/unit/bot/routers/test_start_handler.py`:
  - Не используем aiogram-test (избыточно). Вызываем функции `cmd_start` / `on_contact` напрямую с **mock'ами** Message / FSMContext.
  - `test_cmd_start_new_user_sends_welcome_new_with_contact_keyboard` — `user=None`, mock-ассерт что message.answer вызван с `WELCOME_NEW` и `contact_request()` keyboard.
  - `test_cmd_start_returning_user_sends_main_menu` — `user=...` существующий, ассерт `WELCOME_RETURNING` + `main_menu()`.
  - `test_cmd_start_blocked_user_sends_access_denied` — `user.is_blocked=True`, ассерт `ACCESS_DENIED` + `ReplyKeyboardRemove`.
  - `test_cmd_start_clears_fsm` — мок FSMContext.clear вызван.
- [ ] `tests/unit/bot/routers/test_contact_handler.py`:
  - `test_contact_other_user_rejected` — `message.contact.user_id != message.from_user.id`, ассерт `NEED_OWN_CONTACT` + `contact_request()`.
  - `test_contact_blocked_user_rejected` — user уже в БД и заблокирован.
  - `test_contact_already_registered_shows_main_menu` — user уже зарегистрирован, не новый.
  - `test_contact_happy_path_registers_user_and_shows_main_menu` — mock UserService.register_or_authenticate, ассерт что вызван с правильными полями, и ответ `WELCOME_NEW_REGISTERED` + `main_menu()`.
  - `test_contact_user_not_allowed_sends_phone_not_found` — UserService поднимает `UserNotAllowed`, ассерт `PHONE_NOT_FOUND` + `contact_request()`.
  - `test_contact_registry_unavailable_sends_retry_later` — UserService поднимает `RegistryUnavailableError`, ассерт `REGISTRY_UNAVAILABLE` + `contact_request()`.

  Используй `unittest.mock.AsyncMock` для UserService.register_or_authenticate, простые `Mock` для Message/Contact/FSMContext. Цель — проверить **ветки логики**, не aiogram-runtime.

### Step 5 — Smoke в bot/main

- [ ] Обнови `tests/unit/bot/test_main_smoke.py`:
  - После `build_dispatcher()` проверить, что `dp["registry"]` существует и реализует Protocol.
  - Если этот тест уже проверял число routers — оставь.

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая новые start/contact handler-тесты.
- [ ] `uv run pytest tests/integration -m integration` — без падений.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка локально (опционально, не в DoD):** `make up && make migrate`, в `.env` свежий `TELEGRAM_BOT_TOKEN`, в `infra/mock-registry.yml` добавь свой телефон в `allowed:` или подкинь его через `MOCK_REGISTRY_ALLOWED=+7XXX...`; `uv run python -m src.bot.main`; в TG отправь `/start` → бот просит контакт → отправляешь → видишь главное меню. Проверь сценарий «чужой контакт» (Telegram даёт share контакта другого человека) и «номер не в реестре».
- [ ] Ветка `feature/TASK-011-start-handler`, Conventional Commits:
  - `feat(bot): inject registry via dp workflow-data`
  - `feat(bot): /start handler with contact request flow`
  - `feat(bot): contact handler with registration and domain error handling`
  - `feat(texts): add NEED_OWN_CONTACT, ALREADY_REGISTERED, WELCOME_NEW_REGISTERED`
  - `test(bot): start and contact handler unit tests`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-011-report.md`, задача → `handoff/archive/TASK-011-start-handler/task.md`.

## Артефакты

```
* src/bot/main.py                              # dp["registry"], close on shutdown
* src/bot/routers/start.py                     # cmd_start + on_contact
* src/bot/texts.py                             # +3 константы
+ tests/unit/bot/routers/__init__.py
+ tests/unit/bot/routers/test_start_handler.py
+ tests/unit/bot/routers/test_contact_handler.py
* tests/unit/bot/test_main_smoke.py            # +assert dp["registry"]
```

## Ссылки

- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — sequence «Новый пользователь», edge cases
- [docs/06-external-api.md](../../docs/06-external-api.md) — `ExternalUserRegistryClient`
- [docs/08-conventions.md](../../docs/08-conventions.md) — стиль логов, импорты, фабрики
- [src/shared/services/user.py](../../src/shared/services/user.py) — `register_or_authenticate`
- [src/shared/exceptions.py](../../src/shared/exceptions.py) — `UserNotAllowed`, `RegistryUnavailableError`
- [src/bot/keyboards/__init__.py](../../src/bot/keyboards/__init__.py) — `main_menu`, `contact_request`
- [src/bot/texts.py](../../src/bot/texts.py) — UI-константы

## Подсказки исполнителю

- **aiogram filter for /start:** `from aiogram.filters import CommandStart`. Срабатывает на `/start`, `/start@bot`, `/start payload`.
- **`F.contact`** — фильтр по наличию объекта Contact. Эквивалент: `lambda m: m.contact is not None`.
- **`FSMContext.clear()`** — обнуляет state и data текущего пользователя в RedisStorage.
- **`message.answer(text, reply_markup=...)`** — отправка ответа в тот же чат.
- **`ReplyKeyboardRemove(remove_keyboard=True)`** — снимает клавиатуру (например, при `ACCESS_DENIED`).
- **`Contact` поля**: `phone_number` (без `+` — добавляй сам перед валидацией), `first_name`, `last_name` (Optional), `user_id` (Optional — None если поделились **чужим** контактом). Проверь `user_id == message.from_user.id`.
- **`phone_number` нормализация:** Telegram отдаёт `"71234567890"` (без `+`). Перед вызовом `UserService.register_or_authenticate` нормализуй в E.164 — добавь `+` если его нет. Сервис принимает E.164. Один хелпер в `src/bot/routers/start.py` или в `src/shared/services/user.py` (твоё решение; я бы оставил в handler — это форматирование входа).
- **DI registry через `dp["registry"]`:** aiogram 3 поддерживает `dispatcher["key"] = value` для workflow-data. Handler принимает параметр с именем `registry`, аннотированный как `ExternalUserRegistryClient` — aiogram автоматически инжектит по имени.
- **`dp["registry"].close()` в shutdown**: HTTP-клиент имеет `.close()`, Mock — нет. Сейчас factory может вернуть оба. Проверь `if hasattr(dp["registry"], "close"): await dp["registry"].close()` или `closer = getattr(dp["registry"], "close", None); if closer: await closer()`.
- **Mock'и Message:**
  ```python
  message = MagicMock(spec=Message)
  message.answer = AsyncMock()
  message.from_user = MagicMock(id=12345, username="alice", first_name="Alice")
  message.contact = MagicMock(user_id=12345, phone_number="71111111111", first_name="Alice", last_name=None)
  ```
  `message.from_user` без `assert` лучше mock'ать, чтобы mypy не ругался — в проде это безопасно через assert.
- **Mock UserService:**
  ```python
  user_service_factory = MagicMock(return_value=AsyncMock())
  monkeypatch.setattr("src.bot.routers.start.UserService", user_service_factory)
  ```
  Так и `register_or_authenticate` будет AsyncMock.
- **`phone_hash` для логов:** воспользуйся `hashlib.sha256(phone.encode()).hexdigest()[:8]` или вынеси helper из `src/shared/external/http_registry.py` в `src/shared/utils.py` — на твоё усмотрение. Я бы пока продублировал в handler'е (1 строка), helper введём, когда понадобится в 3-м месте.

## Что НЕ делать

- Не делать обработку других команд (`/events`, `/predict`, и т.п.) — это TASK-012+.
- Не добавлять FSM-states (выбор события/исхода) — это TASK-013.
- Не настраивать APScheduler / напоминания — TASK-017.
- Не подключать webhook.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не добавлять зависимости.
- Не делать integration-тесты с реальным Telegram API (используем mock'и Message).
