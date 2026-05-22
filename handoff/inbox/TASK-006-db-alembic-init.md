---
id: TASK-006
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/03-data-model.md
  - docs/08-conventions.md
  - sessions/2026-05-23-04-task-005-review/decisions.md
priority: high
estimate: L
---

# TASK-006: model tweaks → db.py → Alembic init → 0001_init → integration-тест

## Контекст

TASK-005 описал доменный слой. По итогам review согласованы три минорные правки моделей — их **обязательно применить до автогенерации миграции**, иначе `0001_init` зафиксирует не ту схему. Дальше — async engine/sessionmaker (`src/shared/db.py`), инициализация Alembic, автогенерация первой миграции с ручной вычиткой, удобные Makefile-цели, integration-тест применения миграции на реальной Postgres из CI-service.

Источники: [docs/03-data-model.md](../../docs/03-data-model.md), [docs/08-conventions.md](../../docs/08-conventions.md), решения review — [sessions/2026-05-23-04-task-005-review/decisions.md](../../sessions/2026-05-23-04-task-005-review/decisions.md).

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: обновлённый `state/PROJECT_STATUS.md`, дополненный `state/DECISIONS.md` (шесть новых записей), новая сессия `sessions/2026-05-23-04-task-005-review/`. Упакуй в `chore/post-TASK-005-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-006-db-alembic-init` от свежего `main`.

## Цель

В репо есть `src/shared/db.py` с асинхронным engine и `async_sessionmaker`, проинициализированный Alembic с async-`env.py`, чистая первая миграция `0001_init.py`, набор Makefile-команд для повседневной работы с миграциями, и CI-job, который запускает миграцию на пустой Postgres-service, проверяет схему через introspection и откатывает обратно.

## Definition of Done

### Step 0 — Model tweaks из TASK-005 review (отдельный коммит до db.py)

- [ ] **`src/shared/models/event.py`**: `metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", server_default=text("'{}'::jsonb"), nullable=False)` — убрать `| None` из аннотации.
- [ ] **`src/shared/models/admin_user.py`**: `full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)` (было `Text`).
- [ ] **`src/shared/models/base.py`**: `NAMING_CONVENTION["ck"] = "%(constraint_name)s"` (без авто-префикса).
- [ ] **`src/shared/models/event.py`**: `CheckConstraint(..., name="ck_event_close_before_start")` и `CheckConstraint(..., name="ck_event_result_archive_consistency")` — передавай **полные** имена.
- [ ] Существующие тесты (`tests/unit/models/test_metadata.py`) **уже** проверяют полные имена `ck_event_close_before_start` / `ck_event_result_archive_consistency` — должны остаться зелёными после этого изменения без правок.
- [ ] **Один Conventional-коммит**: `refactor(models): apply tweaks from TASK-005 review (metadata_ NOT NULL, full_name String(128), ck convention)`. Никакой другой работы в этом коммите.

### Step 1 — `src/shared/db.py`

- [ ] Module docstring: «Async engine + sessionmaker для всех сервисов. Используется FastAPI/aiogram через DI (`get_session`).»
- [ ] `engine: AsyncEngine = create_async_engine(str(settings.database_url), echo=False, pool_pre_ping=True)` — `pool_pre_ping=True` спасает от мёртвых соединений после рестарта Postgres.
- [ ] `SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)` — `expire_on_commit=False` обязателен для async, иначе после `commit()` все объекты протухают и любое обращение к атрибуту даст implicit IO.
- [ ] `async def get_session() -> AsyncIterator[AsyncSession]:` — async-генератор, контекст-менеджер открывается через `async with SessionLocal() as session: yield session`. Используется как DI (`Depends(get_session)` в FastAPI, через middleware в aiogram).
- [ ] `__all__ = ["engine", "SessionLocal", "get_session"]`.
- [ ] **НЕТ** глобального `session = SessionLocal()` или подобного. Любой потребитель идёт через `get_session()`.

### Step 2 — Alembic init с async env.py

- [ ] **`alembic.ini`** в корне репо:
  - `[alembic] script_location = src/migrations`
  - `prepend_sys_path = .` (чтобы `src.*` импорты работали в env.py)
  - **Не** ставить `sqlalchemy.url = ...` (URL берётся из settings).
  - Logging-секция стандартная.
- [ ] **`src/migrations/script.py.mako`** (Alembic-шаблон) — оставить дефолтный из `alembic init`.
- [ ] **`src/migrations/env.py`** — переписать на async-вариант:
  - Импортирует `from src.shared.config import settings`
  - Импортирует `from src.shared.models import Base` и устанавливает `target_metadata = Base.metadata`
  - В `run_migrations_online()` использует `create_async_engine(...)` и `async with engine.connect() as conn: await conn.run_sync(do_run_migrations)`
  - `do_run_migrations(connection)` вызывает `context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=False)` + `context.run_migrations()`
  - **`compare_type=True`** — критично, иначе autogenerate пропустит смены типов колонок
  - `include_object=...` фильтр не нужен — у нас одна schema (public)
- [ ] **`src/migrations/versions/`** — папка существует.
- [ ] **`src/migrations/__init__.py`** — пустой, чтобы папка распознавалась как пакет (для импортов из env.py).

### Step 3 — Автогенерация 0001_init и вычитка

- [ ] Поднять локально dev-инфру: `make up`. В `.env` `DATABASE_URL=postgresql+asyncpg://betting:changeme@localhost:5432/betting`.
- [ ] `uv run alembic revision --autogenerate -m "init"` → появляется `src/migrations/versions/<hash>_init.py`. **Переименуй файл и `revision = "..."`** в `0001_init` (стабильный, читаемый префикс).
- [ ] **Ручная вычитка** автогенерированного `upgrade()` / `downgrade()`:
  - Все 8 таблиц на месте, с правильными типами колонок.
  - Все индексы из [docs/03-data-model.md](../../docs/03-data-model.md) присутствуют. Особое внимание: `ix_event_predictions_close_at_active` с `postgresql_where=text("NOT is_archived")` — Alembic иногда упускает partial-index, нужно добавить руками.
  - CHECK constraints `ck_event_close_before_start` и `ck_event_result_archive_consistency`.
  - UNIQUE constraints `uq_user_tg_user_id`, `uq_user_phone`, `uq_category_name`, `uq_category_slug`, `uq_admin_user_login`, `uq_prediction_user_event`.
  - **FK с `use_alter=True`** на `Event.result_outcome_id` → Alembic генерирует операцию `op.create_foreign_key(..., use_alter=True)` отдельно от `create_table`. Проверь, что эта операция есть и идёт **после** обоих `create_table`. Если её нет — добавь руками.
  - `JSONB` на `Event.metadata_` (SQL-имя `metadata`) — `server_default=sa.text("'{}'::jsonb")`.
  - `ARRAY(Integer)` на `ReminderSetting.offsets_minutes`.
  - `downgrade()` симметрично — все drop'ы в обратном порядке, FK с `use_alter` дропается **до** таблиц.
- [ ] **Только один файл миграции** — если autogenerate сгенерил несколько, удали лишние; `0001_init.py` должен содержать всю начальную схему.
- [ ] `down_revision = None`, `branch_labels = None`, `depends_on = None`.
- [ ] Применить миграцию локально: `uv run alembic upgrade head` — без ошибок; `make db.psql` → `\dt` показывает 8 таблиц + `alembic_version`; `\di` — все индексы. Откатить: `uv run alembic downgrade base` — БД пустая (только `alembic_version`).

### Step 4 — Makefile targets

Дополнить корневой `Makefile`:

- [ ] `make migrate` → `uv run alembic upgrade head` (с пояснением в `## …`)
- [ ] `make rollback` → `uv run alembic downgrade -1`
- [ ] `make rollback.all` → `uv run alembic downgrade base` (опасно, можно с подтверждением как у `nuke`, на усмотрение)
- [ ] `make migration.new MSG="..."` → `uv run alembic revision --autogenerate -m "$(MSG)"` (валидация: `[ -n "$(MSG)" ]` иначе ошибка с подсказкой)
- [ ] `make migration.current` → `uv run alembic current`
- [ ] `make migration.history` → `uv run alembic history --verbose`
- [ ] Все цели в `.PHONY`, все с `## …` строкой для `make help`.

### Step 5 — Integration-тест в CI

- [ ] **`tests/integration/__init__.py`** (пустой).
- [ ] **`tests/integration/test_migrations.py`**:
  - Использует `DATABASE_URL` из env (не из `Settings`, чтобы не зависеть от полного `.env`).
  - Перед каждым тестом — `alembic downgrade base` (чистое состояние); после — оставить как есть для следующего теста.
  - `test_upgrade_creates_all_tables`: `alembic upgrade head` → через `AsyncEngine.connect()` сделать SQL `SELECT tablename FROM pg_tables WHERE schemaname='public'` → проверить, что есть все 8 таблиц + `alembic_version`.
  - `test_upgrade_creates_indexes`: проверить наличие `ix_event_predictions_close_at_active` (partial), `ix_event_is_published_is_archived_starts_at`, `uq_prediction_user_event`.
  - `test_upgrade_creates_check_constraints`: `SELECT conname FROM pg_constraint WHERE contype='c'` → есть `ck_event_close_before_start`, `ck_event_result_archive_consistency`.
  - `test_downgrade_drops_everything`: `alembic downgrade base` → таблиц приложения нет (только `alembic_version`).
  - Тесты помечены `@pytest.mark.integration` (зарегистрировать маркер в `pyproject.toml`: `markers = ["integration: tests requiring a real database"]`).
- [ ] **`pyproject.toml` → `[tool.pytest.ini_options]`** добавить `markers = ["integration: tests requiring a real database"]`. Чтобы юнит-тесты не запускали integration по умолчанию, ничего менять не нужно (директория `tests/integration/` собирается тем же `pytest`, но фильтруется маркером).
- [ ] **`.github/workflows/ci.yml`** — новый job `integration`:
  ```yaml
  integration:
    name: Integration (alembic on real postgres)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with: { enable-cache: true }
      - run: uv sync --frozen
      - name: integration tests
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
          # минимум, чтобы Settings импортировался без падения:
          TELEGRAM_BOT_TOKEN: test
          REDIS_URL: redis://localhost:6379/0
          ADMIN_SECRET_KEY: test-secret
        run: uv run pytest tests/integration -m integration -v
  ```
  Это четвёртый job в `ci.yml`, рядом с lint/typecheck/test. Job требует Docker (он есть на `ubuntu-latest`).
- [ ] Локально интеграционные тесты гоняются через `make up` (compose) + `uv run pytest tests/integration -m integration -v` (DATABASE_URL уже в `.env`).

### Качество и workflow

- [ ] `uv run mypy src/shared` — зелёный (включая `db.py` и `migrations/env.py`; для `env.py` можно `# type: ignore` на конкретных alembic-вызовах, если они не типизированы).
- [ ] `uv run ruff check src tests` — зелёный.
- [ ] `uv run ruff format --check src tests` — зелёный.
- [ ] `uv run pytest tests/unit` — все unit-тесты зелёные (22 + новых не появилось).
- [ ] `uv run pytest tests/integration -m integration` — 4 integration-теста зелёные (локально, с поднятой compose).
- [ ] CI на PR — все четыре job'а зелёные (lint, typecheck, test, **integration**).
- [ ] Ветка `feature/TASK-006-db-alembic-init`, Conventional Commits (минимум: Step 0 — `refactor(models): ...`; Step 1 — `feat(shared): add async db engine and sessionmaker`; Step 2-3 — `feat(migrations): init alembic + first migration 0001_init`; Step 4 — `chore(make): add alembic targets`; Step 5 — `test(migrations): integration tests + CI job`).
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-006-report.md`, задача → `handoff/archive/TASK-006-db-alembic-init/task.md`.

## Артефакты

```
* src/shared/models/event.py             # tweak: metadata_ NOT NULL DEFAULT '{}', полные имена ck
* src/shared/models/admin_user.py        # tweak: full_name → String(128)
* src/shared/models/base.py              # tweak: NAMING_CONVENTION["ck"] = "%(constraint_name)s"
+ src/shared/db.py
+ alembic.ini
+ src/migrations/__init__.py
+ src/migrations/env.py                  # async вариант
+ src/migrations/script.py.mako          # дефолт alembic
+ src/migrations/versions/0001_init.py
* Makefile                               # +6 целей migrate/rollback/migration.*
+ tests/integration/__init__.py
+ tests/integration/test_migrations.py
* pyproject.toml                         # markers = ["integration: ..."]
* .github/workflows/ci.yml               # +integration job
```

## Ссылки

- [docs/03-data-model.md](../../docs/03-data-model.md) — источник истины по схеме
- [docs/08-conventions.md](../../docs/08-conventions.md) — структура `src/shared/`, тесты
- [sessions/2026-05-23-04-task-005-review/decisions.md](../../sessions/2026-05-23-04-task-005-review/decisions.md) — детали трёх tweaks
- [ADR-0004](../../docs/adr/0004-no-build-backend.md) — почему `src/migrations/` в репо, а не как installed package

## Подсказки исполнителю

- **`alembic init --template async src/migrations`** даст готовый асинхронный шаблон `env.py`. После — поправь импорт `from src.shared.models import Base` и `target_metadata`. Может потребоваться поправить пути в `script.py.mako` (обычно работает из коробки).
- **`compare_type=True`** в `context.configure(...)` — без него Alembic не заметит, например, смену `Text → String(128)`. Включай.
- **`postgresql_where`** для partial-index Alembic иногда **не** генерирует. После autogenerate ищи `ix_event_predictions_close_at_active` — если просто `Index(..., 'predictions_close_at')`, добавь `postgresql_where=sa.text("NOT is_archived")` руками.
- **`use_alter=True` FK** Alembic выносит в отдельный `op.create_foreign_key(...)`. Проверь, что в `downgrade()` есть симметричный `op.drop_constraint("fk_event_result_outcome_id", "event", type_="foreignkey")` **перед** `op.drop_table("event")`.
- **Async migrations & event loop**: `env.py` создаёт свой event loop через `asyncio.run()`. Не пытайся переиспользовать существующий — alembic запускается отдельным процессом из CLI.
- **Тесты с реальной БД**: каждый тест в `test_migrations.py` должен начинать с чистого состояния. Удобный паттерн — фикстура session-scope, которая делает `alembic downgrade base` в setup; каждый тест запускает свой `upgrade`/`downgrade`. Или function-scope с `downgrade base → upgrade head` в начале каждого. Function-scope медленнее, но проще.
- **`AsyncEngine.connect()` vs `Connection`**: для интроспекции (`SELECT FROM pg_tables`) — `async with engine.connect() as conn: result = await conn.execute(text("..."))`. Сырые SQL — через `text("...")`.
- **conftest.py для integration**: можешь добавить локальный `tests/integration/conftest.py` с фикстурой `async def alembic_clean(...)`, чтобы не дублировать setup в каждом тесте.
- **DATABASE_URL в CI vs local**: в CI job `services.postgres.ports: ['5432:5432']` — host-bind. Localhost из job'а работает. asyncpg DSN — `postgresql+asyncpg://test:test@localhost:5432/test`. **Не** забудь префикс `+asyncpg` — без него engine будет пытаться синхронный psycopg2.
- **`AsyncIterator` импортируется из `typing`** (Python 3.12).
- **Если автогенерация пытается дропнуть наш `metadata_` атрибут как «metadata»** — это потому что Alembic компарит с пустой БД. Не обращай внимания на «drop» — у нас пустая БД, генерация — только `create_*`.

## Что НЕ делать

- Не писать репозитории, сервисы, фабрики, бизнес-логику. Это TASK-007 и далее.
- Не вешать на `engine` глобальные listeners, hooks, plugins, отдельные дашборды. Только то, что в DoD.
- Не подключать `psycopg2` рядом с `asyncpg`. Один драйвер, один режим.
- Не добавлять зависимости: `alembic`, `asyncpg`, `sqlalchemy[asyncio]` уже в `pyproject.toml`.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` (если найдёшь несоответствие — `outbox/TASK-006-question.md`).
- Не оставлять `alembic_version` префиксом случайных hash-ов; имя файла строго `0001_init.py`, `revision = "0001_init"`.
- Не запускать тесты под `pytest -m "not integration"` в основном `test` job CI — оставь дефолтное поведение (тесты integration отделены маркером и идут в свой job). Если pytest начнёт жаловаться на unknown marker — это и есть причина добавления `markers = [...]` в `pyproject.toml`.
