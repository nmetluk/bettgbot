---
id: TASK-009
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/01-architecture.md
  - docs/03-data-model.md
  - docs/04-bot-flows.md
  - docs/05-admin-spec.md
  - docs/06-external-api.md
  - docs/08-conventions.md
priority: high
estimate: L
---

# TASK-009: Сервисный слой — шесть сервисов + доменные исключения

## Контекст

После TASK-008 у нас полный «нижний этаж»: модели, миграция, репозитории, внешний registry. Дальше — слой бизнес-логики, который компонует репозитории, владеет транзакциями и поднимает доменные исключения. Это последний слой перед бот-хендлерами (TASK-010+) и web-роутами (TASK-019+).

Принципы из [docs/08-conventions.md](../../docs/08-conventions.md) и [docs/01-architecture.md](../../docs/01-architecture.md):

- **Сервис получает `AsyncSession` в конструкторе.** Создаёт нужные репозитории сам — handler не должен знать состав.
- **Сервис управляет транзакцией.** Все write-сценарии делают `await session.commit()` в конце успешного пути; при доменном исключении сервис **не** коммитит, поднимает исключение, handler делает `rollback` (или передаёт «как есть» — session-context менеджер сам откатит).
- **Доменные исключения — в `src/shared/exceptions.py`.** Handler ловит их, форматирует ответ; в моделях/репозиториях этих исключений нет.
- **`ExternalUserRegistryClient` — параметр конструктора** у `UserService` (для тестов на `MockExternalUserRegistryClient`).
- **Никакой UI-логики**: сервис не знает про aiogram/FastAPI, не форматирует тексты, не разбирает payload-и Telegram-апдейтов. Только домен.

Источники: модели — [docs/03-data-model.md](../../docs/03-data-model.md); сценарии — [docs/04-bot-flows.md](../../docs/04-bot-flows.md) и [docs/05-admin-spec.md](../../docs/05-admin-spec.md); архитектурный поток — [docs/01-architecture.md](../../docs/01-architecture.md) (sequence-диаграммы «Сделать прогноз», «Зафиксировать итог», «Регистрация»).

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: обновлённые `state/PROJECT_STATUS.md` и `state/DECISIONS.md` (5 новых записей), новая сессия `sessions/2026-05-23-07-task-008-review/`. Упакуй в `chore/post-TASK-008-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-009-services` от свежего `main`.

## Цель

В репо есть:

- `src/shared/exceptions.py` с доменными исключениями.
- Шесть сервисов в `src/shared/services/`: `UserService`, `EventService`, `PredictionService`, `ReminderService`, `StatsService`, `AuditService`.
- `EventService.set_result` — единая транзакция (update event + mark predictions + audit_log).
- Integration-тесты с покрытием happy-path и каждого доменного исключения для каждого сервиса.

## Definition of Done

### Step 0 — Tweaks из TASK-008 review (один коммит до сервисов)

- [ ] **`src/shared/external/http_registry.py`**: `request_id = uuid.uuid4().hex` вынести **из** цикла retry в начало `verify()`. Все попытки одного `verify(phone)` используют один и тот же `X-Request-Id`. Логи и `retry_count` различают попытки и без свежего ID.
- [ ] **`src/shared/external/__init__.py`**: `from functools import lru_cache`; `@lru_cache(maxsize=1) def get_registry_client() -> ExternalUserRegistryClient:`. Существующие тесты `test_factory.py` должны делать `get_registry_client.cache_clear()` между сценариями mock/http; если падают — поправь.
- [ ] **Один Conventional-коммит**: `refactor(external): apply tweaks from TASK-008 review (shared X-Request-Id, cache factory)`. Никакой другой работы в коммите.

### Step 1 — `src/shared/exceptions.py` (доменные исключения)

- [ ] Модуль-docstring + `__all__`.
- [ ] Базовый класс `class DomainError(Exception): ...` — корень иерархии.
- [ ] **Регистрация / пользователь:**
  - `class UserNotAllowed(DomainError)` — телефон не найден / заблокирован во внешнем реестре. Параметры: `reason: str | None`.
  - `class UserBlockedError(DomainError)` — наш `User.is_blocked = true`, попытка действия.
  - `class RegistryUnavailableError(DomainError)` — внешний API вернул `ExternalApiError`. Сервис ловит `ExternalApiError`, оборачивает в свой тип, чтобы handler работал только с доменными типами. `__cause__` сохраняет исходное.
- [ ] **Прогнозы:**
  - `class PredictionDeadlinePassedError(DomainError)`
  - `class EventNotPredictableError(DomainError)` — событие архивно / не опубликовано / не существует. Параметр `reason: Literal["not_found","not_published","archived"]`.
  - `class OutcomeNotForEventError(DomainError)` — переданный `outcome_id` не принадлежит `event_id`.
- [ ] **События (админ):**
  - `class EventNotEnoughOutcomesError(DomainError)` — пытаемся опубликовать с <2 outcomes.
  - `class EventAlreadyHasResultError(DomainError)` — повторная фиксация итога.
  - `class EventNotFoundError(DomainError)`
  - `class OutcomeNotFoundError(DomainError)`
- [ ] **Напоминания:**
  - `class InvalidReminderOffsetsError(DomainError)` — > 5 элементов / отрицательные / < 5 минут / не числа.
- [ ] Все исключения принимают `message` опционально, имеют разумный `__str__`.

### Step 2 — Сервисы

Общий шаблон конструктора:

```python
class UserService:
    """Доменная логика регистрации, блокировки и поиска пользователей."""
    def __init__(self, session: AsyncSession, registry: ExternalUserRegistryClient) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._reminders = ReminderSettingRepository(session)
        self._registry = registry
```

Без базового класса (преждевременно).

#### `src/shared/services/user.py` — `UserService`

- `__init__(session, registry: ExternalUserRegistryClient)`
- `async def register_or_authenticate(*, tg_user_id, phone, first_name, last_name=None, tg_username=None) -> User`:
  1. `user = await self._users.get_by_tg_user_id(tg_user_id)` — если есть, `await self._users.touch_last_seen(user.id)`, **commit**, вернуть.
  2. Иначе вызов `await self._registry.verify(phone)`:
     - `ExternalApiError` → `raise RegistryUnavailableError(...)`
     - `result.is_allowed is False` → `raise UserNotAllowed(reason=result.reason)`
  3. Создать пользователя: `user = await self._users.create(...)`.
  4. Создать дефолтную настройку напоминаний: `await self._reminders.upsert(user_id=user.id, enabled=True, offsets_minutes=[1440, 60])` ([docs/04-bot-flows.md](../../docs/04-bot-flows.md): «по умолчанию `[1440, 60]`»).
  5. **commit**, вернуть `user`.
- `async def touch_last_seen(user_id) -> None` — `await self._users.touch_last_seen(user_id); await self._session.commit()`.
- `async def block(user_id, by_admin_id, *, audit: AuditService) -> None` — `set_blocked(True)` + `audit.log(by_admin_id, "user.block", {"user_id": user_id})` + commit. (См. ниже — `AuditService` принимает session, его передаёт handler.)
  - Альтернатива: `UserService` сам создаёт `AuditLogRepository(self._session)` и делает запись. Так избежим перекрёстной зависимости сервисов. Сделай **именно так** — внутри без `AuditService`.
- `async def unblock(user_id, by_admin_id) -> None` — симметрично.
- `async def list_for_admin(*, query=None, offset=0, limit=50) -> Sequence[User]` — пробрасывает в репо.
- `async def count_for_admin(*, query=None) -> int`.

#### `src/shared/services/event.py` — `EventService`

- `__init__(session)`. Внутри — `EventRepository`, `OutcomeRepository`, `PredictionRepository`, `AuditLogRepository`.
- `async def create_event(*, category_id, title, description, metadata, starts_at, predictions_close_at, by_admin_id) -> Event`:
  - Валидация `predictions_close_at <= starts_at` (DB enforces, но даём раннее доменное `ValueError`/`DomainError` — лучше специфичное `EventValidationError`? Пока — пусть DB-CHECK ловит, сервис не дублирует).
  - Создать событие, записать audit `event.create` с `{event_id, title, category_id}`. Commit.
- `async def update_event(event_id, by_admin_id, **fields) -> None` — `update()` + audit `event.update`.
- `async def publish_event(event_id, by_admin_id) -> None`:
  1. `event = await self._events.get_by_id(event_id)`. Если нет — `EventNotFoundError`.
  2. `count = await self._outcomes.count_by_event(event_id)`. Если `< 2` — `EventNotEnoughOutcomesError`.
  3. `set_published(event_id, True)`. Audit `event.publish`. Commit.
- `async def unpublish_event(event_id, by_admin_id) -> None` — `set_published(False)`. Audit `event.unpublish`. Commit.
- `async def set_result(event_id, outcome_id, by_admin_id) -> int`:
  1. `event = await self._events.get_with_outcomes(event_id)`. `EventNotFoundError` если нет.
  2. Если `event.result_outcome_id is not None` — `EventAlreadyHasResultError`.
  3. Проверить, что `outcome_id` — один из `event.outcomes` (по `id`). Иначе — `OutcomeNotForEventError`.
  4. `await self._events.set_result(event_id, outcome_id, archived_at=datetime.now(tz=UTC))`.
  5. `marked = await self._predictions.mark_correctness(event_id, outcome_id)`.
  6. `await self._audit.add(admin_id=by_admin_id, action="event.set_result", payload={"event_id": event_id, "outcome_id": outcome_id, "marked": marked})`.
  7. `await self._session.commit()`. Вернуть `marked` (для UX-баннера).
- `async def add_outcome(*, event_id, label, sort_order, by_admin_id) -> Outcome` — простой create + audit `outcome.create`.
- `async def update_outcome(outcome_id, by_admin_id, **fields) -> None` — audit `outcome.update`.
- `async def delete_outcome(outcome_id, by_admin_id) -> None` — RESTRICT в БД защитит от удаления при наличии прогнозов; commit'ом ловим `IntegrityError` → доменно конвертируем в `OutcomeNotFoundError`? Нет, в `DomainError` подкласс `OutcomeInUseError`. Добавь его в `exceptions.py`. Audit `outcome.delete`.
- `async def get_event(event_id, *, with_outcomes=False, with_result=False) -> Event | None` — простой read-through.
- `async def list_active(*, category_id=None, offset=0, limit=20) -> Sequence[Event]` — проброс.
- `async def count_active(*, category_id=None) -> int`.
- `async def list_for_admin(...)` / `count_for_admin(...)` — проброс.

#### `src/shared/services/prediction.py` — `PredictionService`

- `__init__(session)`. Внутри — `PredictionRepository`, `EventRepository`.
- `async def make_prediction(*, user_id, event_id, outcome_id) -> Prediction`:
  1. `event = await self._events.get_with_outcomes(event_id)`. Нет — `EventNotPredictableError(reason="not_found")`.
  2. Если `event.is_archived` — `EventNotPredictableError(reason="archived")`.
  3. Если не `event.is_published` — `EventNotPredictableError(reason="not_published")`.
  4. Если `datetime.now(tz=UTC) > event.predictions_close_at` — `PredictionDeadlinePassedError`.
  5. Если `outcome_id not in (o.id for o in event.outcomes)` — `OutcomeNotForEventError`.
  6. `prediction = await self._predictions.upsert(user_id=..., event_id=..., outcome_id=...)`. Commit. Вернуть.
- `async def get_user_prediction(user_id, event_id) -> Prediction | None` — проброс.
- `async def list_active_by_user(user_id, *, offset=0, limit=20) -> Sequence[Prediction]` — проброс.
- `async def list_archived_by_user(user_id, *, offset=0, limit=20) -> Sequence[Prediction]` — проброс.

#### `src/shared/services/reminder.py` — `ReminderService`

- `__init__(session)`. Внутри — `ReminderSettingRepository`.
- `async def get(user_id) -> ReminderSetting | None` — проброс.
- `async def update(*, user_id, enabled, offsets_minutes: list[int]) -> ReminderSetting`:
  - Валидация: `len(offsets) <= 5`, все `int >= 5`, без дубликатов. Иначе — `InvalidReminderOffsetsError`. Сортировать `offsets` по убыванию (UX) перед сохранением.
  - `upsert(...)`. Commit. Вернуть.
- `async def list_users_to_notify(*, offset_minutes) -> Sequence[int]` — проброс к `list_eligible_user_ids`.

#### `src/shared/services/stats.py` — `StatsService`

- `__init__(session)`. Внутри — `PredictionRepository`.
- `async def user_stats(user_id) -> tuple[int, int, float]` — `(correct, total, percent)`. `percent = round(correct / total * 100, 1) if total else 0.0`.

#### `src/shared/services/audit.py` — `AuditService`

- `__init__(session)`. Внутри — `AuditLogRepository`.
- `async def add(*, admin_id, action, payload) -> AuditLog` — проброс. Commit **не** делает (caller-сервис управляет).
- `async def list(*, admin_id=None, action=None, since=None, until=None, offset=0, limit=50) -> Sequence[AuditLog]` — проброс.
- `async def count(*, ...)` — проброс.

> **Замечание:** `AuditService` — это «обёртка над репозиторием», но имеет смысл как точка входа из admin-UI (TASK-026). Внутри других сервисов аудит-запись делается напрямую через `AuditLogRepository(self._session).add(...)`, **не** через `AuditService`, чтобы не плодить инстансы и не путать транзакционные границы. Это явно зафиксировано: каждый сервис, который делает audit-запись, импортирует `AuditLogRepository` напрямую.

### Step 3 — `src/shared/services/__init__.py`

- [ ] Re-export всех шести сервисов, `__all__`, module-docstring.

### Step 4 — Integration-тесты

`tests/integration/services/`:

- [ ] `tests/integration/services/__init__.py` (пустой).
- [ ] `tests/integration/services/conftest.py` — фикстура `mock_registry` (in-memory `MockExternalUserRegistryClient` для `UserService`-тестов).

**Покрытие** (пишем happy-path + каждое доменное исключение):

- [ ] `test_user_service.py`:
  - `register_or_authenticate` happy для нового пользователя — создаёт `User` + дефолтный `ReminderSetting([1440, 60])` + touches last_seen.
  - registry → `not_found` → `UserNotAllowed`.
  - registry → `blocked` → `UserNotAllowed(reason="blocked"...)`.
  - registry → `ExternalApiError` → `RegistryUnavailableError` с правильным `__cause__`.
  - повторная регистрация существующего → не создаёт второй raw / dup, обновляет last_seen.
  - `block/unblock` — пишут audit.
- [ ] `test_event_service.py`:
  - `publish_event` без outcomes → `EventNotEnoughOutcomesError`.
  - `publish_event` с одним outcome → `EventNotEnoughOutcomesError`.
  - `publish_event` с двумя — успех + audit.
  - `set_result` happy: помечает `is_archived`, `result_outcome_id`, проставляет `is_correct` на двух разных прогнозах (один с правильным outcome — true; другой — false), audit с `marked=2`.
  - `set_result` второй раз → `EventAlreadyHasResultError`.
  - `set_result` с чужим outcome → `OutcomeNotForEventError`.
  - `delete_outcome` с прогнозами → `OutcomeInUseError`.
- [ ] `test_prediction_service.py`:
  - happy `make_prediction` — создаёт.
  - повторный `make_prediction` другим outcome — обновляет (upsert).
  - `event.is_archived` → `EventNotPredictableError(reason="archived")`.
  - `not is_published` → `EventNotPredictableError(reason="not_published")`.
  - `not exists` → `EventNotPredictableError(reason="not_found")`.
  - дедлайн прошёл → `PredictionDeadlinePassedError` (используй `freezegun` или передавай `predictions_close_at` в прошлом).
  - чужой outcome → `OutcomeNotForEventError`.
- [ ] `test_reminder_service.py`:
  - happy `update`: 6 элементов → `InvalidReminderOffsetsError`.
  - элемент `< 5` → ошибка.
  - дубликаты → ошибка.
  - валидный список сортируется по убыванию.
- [ ] `test_stats_service.py`:
  - пустой user — `(0, 0, 0.0)`.
  - 2 correct / 5 total → `(2, 5, 40.0)`.
- [ ] `test_audit_service.py`:
  - `add` сохраняет запись (с commit вне сервиса — в тесте делаем `await session.commit()` после).
  - `list` фильтрует по `admin_id`, `action`, окну дат.

### Качество и workflow

- [ ] `uv run mypy src/shared` — зелёный (strict).
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — 41 unit-теста.
- [ ] `uv run pytest tests/integration -m integration` — 4 migrations + 33 repos + новые services.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] Ветка `feature/TASK-009-services`, Conventional Commits. Минимум:
  - `refactor(external): apply tweaks from TASK-008 review` (Step 0)
  - `feat(shared): domain exceptions`
  - `feat(services): user, event, prediction, reminder, stats, audit`
  - `test(services): integration tests for happy paths and domain exceptions`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-009-report.md`, задача → `handoff/archive/TASK-009-services/task.md`.

## Артефакты

```
* src/shared/external/http_registry.py       # shared X-Request-Id (Step 0)
* src/shared/external/__init__.py            # @lru_cache(maxsize=1) (Step 0)
+ src/shared/exceptions.py
+ src/shared/services/__init__.py
+ src/shared/services/user.py
+ src/shared/services/event.py
+ src/shared/services/prediction.py
+ src/shared/services/reminder.py
+ src/shared/services/stats.py
+ src/shared/services/audit.py
+ tests/integration/services/__init__.py
+ tests/integration/services/conftest.py
+ tests/integration/services/test_user_service.py
+ tests/integration/services/test_event_service.py
+ tests/integration/services/test_prediction_service.py
+ tests/integration/services/test_reminder_service.py
+ tests/integration/services/test_stats_service.py
+ tests/integration/services/test_audit_service.py
```

## Ссылки

- [docs/01-architecture.md](../../docs/01-architecture.md) — sequence-диаграммы «Сделать прогноз», «Зафиксировать итог», «Регистрация»; «единая бизнес-логика», «транзакции в сервисе»
- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — `register_or_authenticate` сценарии, дефолтные `[1440, 60]` напоминания
- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — `set_result` поведение, audit-логи
- [docs/08-conventions.md](../../docs/08-conventions.md) — слои, доменные исключения, `datetime.now(tz=UTC)`
- [src/shared/exceptions.py] — создаётся в Step 1
- [src/shared/external/](../../src/shared/external/) — `ExternalUserRegistryClient` для DI

## Подсказки исполнителю

- **Импорт `ExternalUserRegistryClient` в `UserService`** — из `src.shared.external.registry`, **не** из `src.shared.external` (последний дёрнет фабрику через side-effect — мы хотим только тип).
- **`datetime.now(tz=UTC)`** обязательно с timezone. `datetime.utcnow()` запрещён конвенциями.
- **Transactional `set_result`:** все шаги в одном `try` — если что-то падает, исключение пробрасывается, сервис **не коммитит**, контекст-менеджер сессии откатит. Commit — только после `await self._audit.add(...)`.
- **`session.commit()` в каждом write-методе сервиса** — стандартный паттерн. Read-методы — без commit.
- **`upsert` в `PredictionRepository.upsert`** уже делает `RETURNING + refresh`. Сервис только делает commit.
- **Тесты:** session-фикстура из `tests/integration/conftest.py` делает rollback в финале — если в сервисе есть `commit()`, он применит к savepoint в рамках сессии. **Не** дублируй commit в тестах.

  Hmm, нюанс: сервис `commit()` коммитит транзакцию сессии, после чего фикстура `rollback()` не сможет откатить уже зафиксированное. Решение — использовать `SAVEPOINT`-обёртку. Самый чистый вариант: в session-фикстуре открыть `await session.begin_nested()`, и сервисный `commit()` коммитит savepoint, а внешняя транзакция всё равно откатывается при `engine.dispose()`.

  Реализация фикстуры для services-тестов (в `tests/integration/services/conftest.py`):
  ```python
  @pytest_asyncio.fixture()
  async def session() -> AsyncIterator[AsyncSession]:
      from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
      from sqlalchemy.pool import NullPool
      from src.shared.config import settings

      engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
      sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
      async with engine.connect() as conn:
          trans = await conn.begin()
          session = AsyncSession(bind=conn, expire_on_commit=False)
          await session.begin_nested()
          # ловим конец savepoint — каждый commit сервиса откроет новый savepoint
          from sqlalchemy import event as sa_event

          @sa_event.listens_for(session.sync_session, "after_transaction_end")
          def _restart_savepoint(sess, transaction):
              if transaction.nested and not transaction._parent.nested:
                  sess.begin_nested()

          try:
              yield session
          finally:
              await session.close()
              await trans.rollback()
              await engine.dispose()
  ```
  Эта формула — стандартный pytest-asyncio + SQLAlchemy "transaction-rollback fixture". Перенеси в `tests/integration/services/conftest.py` или в общий `tests/integration/conftest.py` под отдельным именем (например `nested_session`) — на твой выбор.

- **Мок registry для UserService-тестов:** реализация `ExternalUserRegistryClient` Protocol — простой класс на ~10 строк:
  ```python
  class StubRegistry:
      def __init__(self, result: VerificationResult | None = None, raises: Exception | None = None):
          self._result = result
          self._raises = raises
      async def verify(self, phone: str) -> VerificationResult:
          if self._raises is not None:
              raise self._raises
          assert self._result is not None
          return self._result
  ```
- **Audit-запись внутри других сервисов** — через `AuditLogRepository(self._session).add(...)`, **не** через `AuditService`. Это в task явно прописано выше.
- **`update_event(**fields)`** — пробрасывает в репо. Не валидируй здесь, какие поля можно менять (это TASK админки). Сервис — про логику инвариантов, а не per-field whitelist.

## Что НЕ делать

- Не писать `CategoryService`, `OutcomeService` (как отдельные классы — методы outcome'ов есть в EventService), `AdminAuthService`. Это придёт с admin-задачами (TASK-019+).
- Не подключать `injector`, `dependency-injector` или другие DI-библиотеки. Простая инъекция через конструктор достаточна.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не добавлять зависимости (`freezegun` уже есть, остальное — из стандартной библиотеки и существующих deps).
- Не подключать сервис к real-time middleware aiogram/FastAPI — это TASK-010 и TASK-019.
- Не делать handler-вызовы прямо в сервисах — никаких `await message.answer(...)`.
