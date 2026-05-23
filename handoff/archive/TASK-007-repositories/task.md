---
id: TASK-007
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/01-architecture.md
  - docs/03-data-model.md
  - docs/04-bot-flows.md
  - docs/05-admin-spec.md
  - docs/08-conventions.md
priority: high
estimate: L
---

# TASK-007: Репозитории — тонкий query-слой над агрегатами

## Контекст

После TASK-006 у нас есть БД-схема и async-engine. Дальше — тонкий query-слой, который сервисы (TASK-008) будут использовать. Принципы из [docs/08-conventions.md](../../docs/08-conventions.md) и [docs/01-architecture.md](../../docs/01-architecture.md):

- **Один репозиторий — один агрегат.** 8 классов под 8 моделей.
- **`AsyncSession` в конструкторе.** Не получаем сессию параметром каждого метода — берём один раз.
- **NO commit/rollback внутри.** Сессией владеет вызывающий (сервис). Репозиторий делает `add`, `flush`, `execute`, `scalar`, `scalars` — но не управляет транзакцией.
- **Возвращаем ORM-инстансы.** Никаких DTO-преобразований, никаких словарей. Сервис при необходимости конвертирует.
- **Eager-loading явно.** В async-моде ленивые загрузки запрещены — каждый метод, который должен вернуть связанные сущности, явно говорит это через `selectinload(...)` / `joinedload(...)` (или предлагает опциональный параметр `with_*`).
- **Никакой бизнес-логики.** Только SELECT/INSERT/UPDATE/DELETE по структуре агрегата. Решения «можно ли менять прогноз после дедлайна» / «есть ли минимум 2 outcome у Event для публикации» — это TASK-008.

Источники истины: модель — [docs/03-data-model.md](../../docs/03-data-model.md); сценарии, которые будут вызывать эти методы — [docs/04-bot-flows.md](../../docs/04-bot-flows.md) и [docs/05-admin-spec.md](../../docs/05-admin-spec.md).

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: обновлённые `state/PROJECT_STATUS.md` (закрытие TASK-006, новые шаги), `state/DECISIONS.md` (шесть новых записей), переписанный `state/BACKLOG.md` (renumbering), новая сессия `sessions/2026-05-23-05-task-006-review/`. Упакуй в `chore/post-TASK-006-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-007-repositories` от свежего `main`.

## Цель

В `src/shared/repositories/` восемь репозиториев. Каждый покрыт integration-тестами против реального Postgres через session-fixture с rollback после теста. Все методы async, типизированы строго, без бизнес-логики.

## Definition of Done

### Структура

- [ ] `src/shared/repositories/__init__.py` — re-export всех классов, `__all__`, module-docstring.
- [ ] По одному файлу на репозиторий:
  - `user.py` → `UserRepository`
  - `category.py` → `CategoryRepository`
  - `event.py` → `EventRepository`
  - `outcome.py` → `OutcomeRepository`
  - `prediction.py` → `PredictionRepository`
  - `reminder_setting.py` → `ReminderSettingRepository`
  - `admin_user.py` → `AdminUserRepository`
  - `audit_log.py` → `AuditLogRepository`
- [ ] Общий шаблон конструктора:
  ```python
  class UserRepository:
      """Запросы к таблице `user`. Не управляет транзакциями."""
      def __init__(self, session: AsyncSession) -> None:
          self._session = session
  ```
  Без базового класса (если не возникнет осмысленного `BaseRepository[T]` — не вводить).

### Методы по репозиториям

**Принцип:** включаем только то, что действительно нужно ближайшим задачам ([docs/04-bot-flows.md](../../docs/04-bot-flows.md), [docs/05-admin-spec.md](../../docs/05-admin-spec.md)). Добавлять методы по требованию.

#### `UserRepository`
- `get_by_id(user_id: int) -> User | None`
- `get_by_tg_user_id(tg_user_id: int) -> User | None` — главный read-путь для middleware бота
- `get_by_phone(phone: str) -> User | None`
- `create(*, tg_user_id: int, phone: str, tg_username: str | None, first_name: str, last_name: str | None) -> User` — добавляет в сессию, делает `flush` (чтобы получить `id`), возвращает инстанс
- `touch_last_seen(user_id: int) -> None` — `UPDATE user SET last_seen_at = now() WHERE id = ...`
- `set_blocked(user_id: int, blocked: bool) -> None`
- `list_for_admin(*, query: str | None = None, offset: int = 0, limit: int = 50) -> Sequence[User]` — поиск по `phone` substring + `tg_username` substring + `first_name`/`last_name` ILIKE; пагинация
- `count_for_admin(*, query: str | None = None) -> int` — для пагинатора

#### `CategoryRepository`
- `get_by_id(category_id: int) -> Category | None`
- `get_by_slug(slug: str) -> Category | None`
- `list(*, active_only: bool = False) -> Sequence[Category]` — отсортировано по `sort_order, id`
- `create(*, name: str, slug: str, sort_order: int = 0, is_active: bool = True) -> Category`
- `update(category_id: int, **fields: Any) -> None` — простой UPDATE по `**fields`; в сервисе проверим, что меняются только разрешённые ключи
- `delete(category_id: int) -> None` — RESTRICT гарантирует, что удалится только пустая

#### `EventRepository`
- `get_by_id(event_id: int) -> Event | None` — без подгрузки связанных
- `get_with_outcomes(event_id: int) -> Event | None` — `selectinload(Event.outcomes)`
- `get_with_result(event_id: int) -> Event | None` — `selectinload(Event.result_outcome)`
- `list_active(*, category_id: int | None = None, offset: int = 0, limit: int = 20) -> Sequence[Event]` — `is_published = true AND is_archived = false`, сортировка по `starts_at`
- `count_active(*, category_id: int | None = None) -> int`
- `list_for_admin(*, category_id: int | None = None, status: Literal["all","draft","published_open","published_closed","archived"] = "all", offset: int = 0, limit: int = 50) -> Sequence[Event]` — фильтры через `is_published`/`is_archived`/`predictions_close_at vs now()`
- `count_for_admin(...)`
- `create(*, category_id: int, title: str, description: str | None, metadata: dict[str, Any] | None, starts_at: datetime, predictions_close_at: datetime, created_by_admin_id: int) -> Event`
- `update(event_id: int, **fields: Any) -> None`
- `set_published(event_id: int, published: bool) -> None`
- `set_result(event_id: int, outcome_id: int, archived_at: datetime) -> None` — UPDATE без логики «правильно ли это». Логику оборачивает сервис в транзакцию с `PredictionRepository.mark_correctness` и `AuditLogRepository.add`
- `list_with_deadline_in_window(*, since: datetime, until: datetime) -> Sequence[Event]` — для планировщика напоминаний; `is_published = true AND is_archived = false AND predictions_close_at BETWEEN since AND until`

#### `OutcomeRepository`
- `get_by_id(outcome_id: int) -> Outcome | None`
- `list_by_event(event_id: int) -> Sequence[Outcome]` — отсортировано `sort_order, id`
- `count_by_event(event_id: int) -> int`
- `create(*, event_id: int, label: str, sort_order: int = 0) -> Outcome`
- `update(outcome_id: int, **fields: Any) -> None`
- `delete(outcome_id: int) -> None` — RESTRICT гарантирует, что не упадёт под прогнозом

#### `PredictionRepository`
- `get_by_user_event(user_id: int, event_id: int) -> Prediction | None`
- `upsert(*, user_id: int, event_id: int, outcome_id: int) -> Prediction` — `INSERT ... ON CONFLICT (user_id, event_id) DO UPDATE SET outcome_id = EXCLUDED.outcome_id, updated_at = now() RETURNING *`. Используй `pg_insert` из `sqlalchemy.dialects.postgresql`
- `list_active_by_user(user_id: int, *, offset: int = 0, limit: int = 20) -> Sequence[Prediction]` — JOIN на Event, `event.is_archived = false`, сортировка по `event.starts_at`
- `list_archived_by_user(user_id: int, *, offset: int = 0, limit: int = 20) -> Sequence[Prediction]` — `event.is_archived = true`
- `mark_correctness(event_id: int, correct_outcome_id: int) -> int` — `UPDATE prediction SET is_correct = (outcome_id = :correct) WHERE event_id = :event` → возвращает `rowcount`. Сервис вызовет это внутри транзакции `set_result`
- `user_stats(user_id: int) -> tuple[int, int]` — `SELECT count(*) FILTER (WHERE is_correct = true), count(*) WHERE user_id = ? AND is_correct IS NOT NULL` → `(correct, total)`
- `users_without_prediction_for_event(event_id: int) -> Sequence[int]` — `SELECT u.id FROM user u WHERE u.is_blocked = false AND NOT EXISTS (SELECT 1 FROM prediction p WHERE p.user_id = u.id AND p.event_id = :event)`. Для планировщика напоминаний

#### `ReminderSettingRepository`
- `get_by_user(user_id: int) -> ReminderSetting | None`
- `upsert(*, user_id: int, enabled: bool, offsets_minutes: list[int]) -> ReminderSetting` — `INSERT ... ON CONFLICT (user_id) DO UPDATE`
- `list_eligible_user_ids(*, offset_minutes: int) -> Sequence[int]` — для планировщика: `SELECT user_id FROM reminder_setting WHERE enabled = true AND :offset = ANY(offsets_minutes)`

#### `AdminUserRepository`
- `get_by_id(admin_id: int) -> AdminUser | None`
- `get_by_login(login: str) -> AdminUser | None` — главный путь login flow
- `create(*, login: str, password_hash: str, full_name: str | None) -> AdminUser`
- `touch_last_login(admin_id: int) -> None`

#### `AuditLogRepository`
- `add(*, admin_id: int, action: str, payload: dict[str, Any]) -> AuditLog` — `add` + `flush` (чтобы получить `id`); commit — на сервисе
- `list(*, admin_id: int | None = None, action: str | None = None, since: datetime | None = None, until: datetime | None = None, offset: int = 0, limit: int = 50) -> Sequence[AuditLog]`
- `count(*, admin_id: int | None = None, action: str | None = None, since: datetime | None = None, until: datetime | None = None) -> int`

### Тесты

`tests/integration/repositories/`:

- [ ] `tests/integration/conftest.py` — общая фикстура `session`:
  ```python
  @pytest_asyncio.fixture()
  async def session() -> AsyncIterator[AsyncSession]:
      """Открывает сессию, прогоняет тест, делает rollback — данные не сохраняются."""
      async with SessionLocal() as session:
          try:
              yield session
          finally:
              await session.rollback()
  ```
  + helper-фабрики (без factory-boy, простые функции):
  ```python
  async def make_admin(session: AsyncSession, **overrides: Any) -> AdminUser: ...
  async def make_category(session: AsyncSession, **overrides: Any) -> Category: ...
  async def make_user(session: AsyncSession, **overrides: Any) -> User: ...
  async def make_event(session: AsyncSession, **overrides: Any) -> Event: ...
  async def make_outcome(session: AsyncSession, event_id: int, **overrides: Any) -> Outcome: ...
  ```
  Они делают `session.add` + `session.flush()`, возвращают инстанс. Уникальные поля (login, phone, slug) генерируем через counter / uuid.

- [ ] `tests/integration/repositories/__init__.py` (пустой).

- [ ] `test_user_repository.py` (минимум): create+get_by_tg_id round-trip; get_by_phone после create; touch_last_seen меняет `last_seen_at`; set_blocked; list_for_admin фильтрует по query; UNIQUE constraint на `tg_user_id` — `IntegrityError`.

- [ ] `test_category_repository.py`: create, list active_only, update, get_by_slug, delete пустой; delete с привязанным Event падает RESTRICT.

- [ ] `test_event_repository.py`: create + get_by_id; get_with_outcomes возвращает eager outcomes; list_active фильтрует `is_published`/`is_archived`; list_for_admin со status="draft"; set_result обновляет поля; list_with_deadline_in_window.

- [ ] `test_outcome_repository.py`: list_by_event сортировка; delete защищён RESTRICT (есть Prediction).

- [ ] `test_prediction_repository.py`: upsert — INSERT затем UPDATE для той же (user, event); mark_correctness корректно проставляет true/false; user_stats; list_active_by_user / list_archived_by_user; users_without_prediction_for_event.

- [ ] `test_reminder_setting_repository.py`: upsert (insert и update), list_eligible_user_ids с разными offset'ами и `enabled = false`.

- [ ] `test_admin_user_repository.py`: create + get_by_login; UNIQUE login; touch_last_login.

- [ ] `test_audit_log_repository.py`: add возвращает с id; list с фильтрами; count.

- [ ] Все тесты помечены маркером `integration` (через `pytestmark = pytest.mark.integration` в файле или в conftest).

- [ ] **CI job `integration`** уже существует — новые тесты подцепятся автоматически. Проверь, что время прогона разумное (ожидание: до ~30с локально, до минуты в CI).

### Качество и workflow

- [ ] `uv run mypy src/shared` — зелёный (strict). Используй `Sequence[T]` для возврата списков, `AsyncSession` параметр явно.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — 22 unit-теста как и были.
- [ ] `uv run pytest tests/integration -m integration` — все integration зелёные (4 старых migrations + новые repositories).
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] Ветка `feature/TASK-007-repositories`, Conventional Commits. Минимум один коммит на тематический блок:
  - `feat(repositories): user repository`
  - `feat(repositories): category repository`
  - ... и т.д.
  - Или один коммит на «все 8 репозиториев» — тоже допустимо, по твоему усмотрению.
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-007-report.md`, задача → `handoff/archive/TASK-007-repositories/task.md`.

## Артефакты

```
+ src/shared/repositories/__init__.py
+ src/shared/repositories/user.py
+ src/shared/repositories/category.py
+ src/shared/repositories/event.py
+ src/shared/repositories/outcome.py
+ src/shared/repositories/prediction.py
+ src/shared/repositories/reminder_setting.py
+ src/shared/repositories/admin_user.py
+ src/shared/repositories/audit_log.py
+ tests/integration/conftest.py
+ tests/integration/repositories/__init__.py
+ tests/integration/repositories/test_user_repository.py
+ tests/integration/repositories/test_category_repository.py
+ tests/integration/repositories/test_event_repository.py
+ tests/integration/repositories/test_outcome_repository.py
+ tests/integration/repositories/test_prediction_repository.py
+ tests/integration/repositories/test_reminder_setting_repository.py
+ tests/integration/repositories/test_admin_user_repository.py
+ tests/integration/repositories/test_audit_log_repository.py
```

## Ссылки

- [docs/01-architecture.md](../../docs/01-architecture.md) — Handler → Service → Repository → Model
- [docs/03-data-model.md](../../docs/03-data-model.md) — поля и индексы
- [docs/04-bot-flows.md](../../docs/04-bot-flows.md) — какие запросы понадобятся
- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — фильтры/пагинация для админки
- [docs/08-conventions.md](../../docs/08-conventions.md) — «никакой бизнес-логики в репозитории», «транзакции — в сервисе»

## Подсказки исполнителю

- **`AsyncSession` запросы:** `result = await self._session.execute(select(User).where(...))` → `result.scalars().all()` / `result.scalar_one_or_none()` / `result.scalar_one()`.
- **`flush()` vs `commit()`:** репозиторий вызывает `await self._session.flush()` после `add(...)` — это пушит INSERT в БД, заполняет `id`, но не коммитит. Service делает `await session.commit()` в конце сценария.
- **Eager-loading в async:** `select(Event).options(selectinload(Event.outcomes)).where(Event.id == ...)`. **Никогда** не возвращай `Event` без явной загрузки `outcomes`, если ожидается, что вызывающий к ним обратится.
- **`pg_insert` для upsert:**
  ```python
  from sqlalchemy.dialects.postgresql import insert as pg_insert
  stmt = (
      pg_insert(Prediction)
      .values(user_id=..., event_id=..., outcome_id=...)
      .on_conflict_do_update(
          index_elements=["user_id", "event_id"],
          set_={"outcome_id": ..., "updated_at": func.now()},
      )
      .returning(Prediction)
  )
  result = await self._session.execute(stmt)
  return result.scalar_one()
  ```
- **`mark_correctness`:**
  ```python
  stmt = (
      update(Prediction)
      .where(Prediction.event_id == event_id)
      .values(is_correct=(Prediction.outcome_id == correct_outcome_id))
  )
  result = await self._session.execute(stmt)
  return result.rowcount
  ```
  Альтернативно — `text("UPDATE prediction SET is_correct = (outcome_id = :correct) WHERE event_id = :event")`. Через `update()` чище и типизировано.
- **`users_without_prediction_for_event`:** `NOT EXISTS` — стандартный приём, использует индекс `uq_prediction_user_event`.
- **`list_eligible_user_ids`:** `:offset = ANY(offsets_minutes)` — это `from sqlalchemy import any_` или `Column.any_(offset)`. Проверь синтаксис; альтернатива — text-выражение `text("CAST(:offset AS INTEGER) = ANY(offsets_minutes)")`.
- **Pagination:** `offset+limit` — стандартно. Для будущей оптимизации (deep pagination) можно перейти на keyset, но не сейчас.
- **`Sequence[T]` vs `list[T]`:** возвращай `Sequence[T]` — это immutable-friendly интерфейс, мешает вызывающему случайно мутировать список из БД.
- **Уникальность в фабриках:** простой счётчик + thread-safe увеличение — или `uuid.uuid4().int & ((1<<63)-1)` для `tg_user_id`/`phone`. На тестах rollback всё снесёт.
- **factory-boy** не вводим в этой задаче. Helper-функции в conftest достаточны; перейдём на factory-boy, если станет совсем многословно.
- **Сессии в тестах:** одна сессия на тест (`session` фикстура), `rollback` в финале — данные не сохраняются. Это даёт независимость тестов. Если очень захочется коммитить — оборачивай в SAVEPOINT (`async with session.begin_nested(): ...`), но в этой задаче не нужно.
- **Импорт `User`, `Event` и т.д.** — из `src.shared.models`.

## Что НЕ делать

- Не писать сервисы (`UserService`, ...) — это TASK-008.
- Не управлять транзакциями внутри репозитория (`commit`/`rollback`).
- Не вводить базовый `BaseRepository[T]` — преждевременно. У нас 8 разных профилей методов.
- Не подключать factory-boy в зависимости (он уже в `pyproject.toml` как dev-deps, но не вводим в код).
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не выходить за периметр методов из этого DoD. Если кажется, что какой-то метод тоже нужен — выноси в открытый вопрос отчёта, не добавляй молча.
