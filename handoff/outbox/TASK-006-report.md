---
task: TASK-006
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/14
branch: feature/TASK-006-db-alembic-init
commits:
  - 4593d9d refactor(models): apply tweaks from TASK-005 review
  - 808cb86 feat(shared): add async db engine and sessionmaker
  - 07c85b7 feat(migrations): init alembic + first migration 0001_init
  - 4e639b5 chore(make): add alembic targets
  - 936e1be test(migrations): integration tests + CI job
  - 7edd054 chore(handoff): mark TASK-006 in-progress
---

# Отчёт по TASK-006: model tweaks → db.py → Alembic init → 0001_init → integration-тест

## Сводка

Закрыты сразу несколько слоёв: применены три tweaks моделей по итогам TASK-005-review (Step 0); поднят async-engine + sessionmaker в `src/shared/db.py` (Step 1); Alembic инициализирован с async-`env.py`, читающим URL из `Settings` (Step 2); автогенерация дала ожидаемый diff, после ручной вычитки `0001_init.py` имеет все 8 таблиц с правильными типами/индексами/CHECK constraints/FK; циклическая FK `fk_event_result_outcome_id` (с `use_alter`) вынесена в отдельный `op.create_foreign_key` после создания обеих таблиц, в `downgrade` дропается **первой** (Step 3); Makefile пополнился шестью целями (Step 4); добавлен новый CI job `integration` с postgres:16 service-container, четыре теста проверяют схему через `pg_tables`/`pg_indexes`/`pg_constraint` (Step 5).

Главный сюрприз — конфликт top-level `tests/conftest.py` (где жил stub-env для unit-тестов) с integration-тестами: `os.environ.setdefault` перетирал реальный `DATABASE_URL` ещё до того, как integration-тесты получали управление. Решение — перенести stubs в `tests/unit/conftest.py`, а integration-тестам дать собственный мини-loader `.env` на module-level (для локального запуска) и `env:`-блок в CI workflow (для CI). Это явно вынесено в открытый вопрос ниже.

Pre-task cleanup PR [#13](https://github.com/nmetluk/bettgbot/pull/13) свернул накопившиеся правки cowork (six DECISIONS-записей, sessions/2026-05-23-04, обновление PROJECT_STATUS) перед основной работой.

## Изменённые файлы

```
* src/shared/models/base.py                # ck convention → %(constraint_name)s
* src/shared/models/event.py               # metadata_ NOT NULL DEFAULT '{}', полные имена ck
* src/shared/models/admin_user.py          # full_name → String(128)
+ src/shared/db.py                         # async engine + sessionmaker + get_session
+ alembic.ini                              # sqlalchemy.url закомментирован
+ src/migrations/__init__.py               # пустой пакет
+ src/migrations/env.py                    # async вариант, URL из settings
+ src/migrations/script.py.mako            # дефолтный шаблон alembic
+ src/migrations/versions/0001_init.py     # начальная схема
- src/migrations/.gitkeep
* Makefile                                 # +migrate/rollback/rollback.all/migration.*
* pyproject.toml                           # markers = ["integration: ..."]
+ tests/integration/__init__.py
+ tests/integration/test_migrations.py     # 4 теста через pg_tables/pg_indexes/pg_constraint
- tests/conftest.py                        # переехал →
+ tests/unit/conftest.py                   # ← теперь stub-env только для unit
* .github/workflows/ci.yml                 # +integration job, test job фильтрует -m "not integration"
* handoff/inbox/TASK-006-db-alembic-init.md → in-progress → archive
+ handoff/archive/TASK-006-db-alembic-init/task.md
+ handoff/outbox/TASK-006-report.md
```

## Тесты и CI

```
ruff check src tests               All checks passed!
ruff format --check src tests      28 files already formatted
mypy src/shared (strict)           Success: no issues found in 14 source files
pytest -m "not integration"        22 passed, 4 deselected in 0.23s
pytest tests/integration -m integration
                                   4 passed in 3.87s
```

CI PR [#14](https://github.com/nmetluk/bettgbot/pull/14) — все четыре job'а зелёные:
- Lint (ruff)
- Typecheck (mypy)
- Tests (pytest, unit) — `-m "not integration"`
- Integration (alembic on real postgres) — 34с с postgres:16 service-container

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env

# Поднять БД и применить миграцию
make up
make migrate            # alembic upgrade head
make migration.current  # 0001_init (head)

# psql сверка
make db.psql            # \dt → 9 таблиц; \di → 24 индекса; \d event → CHECK ck_event_*

# Откат
make rollback           # downgrade -1
# или
make rollback.all       # downgrade base (с подтверждением ROLLBACK)

# Тесты
uv run pytest -m "not integration"                    # unit (22)
uv run pytest tests/integration -m integration -v     # integration (4)
```

## Что не сделано / вынесено

1. **Лениво созданный engine** — `engine` создаётся при импорте `src.shared.db`. Если в каком-то пути импорт случится без `.env` (например, в тестах, которые не используют БД, но импортируют что-то транзитивно), Settings() сломается. Сейчас все тестовые пути защищены conftest'ом. Если нужна явная защита — `get_engine()` lazy. Не делал в этой задаче.
2. **`alembic` запускается subprocess'ом в тестах** — стабильнее, но медленнее in-process `alembic.command.upgrade(Config(...), ...)`. На MVP-схеме 4 теста ~3.5с — приемлемо.
3. **`_load_dotenv` в integration-тесте — собственный мини-парсер**, не подключал `python-dotenv` как dev-deps. Если cowork предпочитает явную зависимость — добавлю.
4. **Никакой бизнес-логики**: репозитории/сервисы/фабрики/seed-data — TASK-007+.

## Открытые вопросы для проектировщика

1. **`tests/conftest.py` → `tests/unit/conftest.py`.** DoD не предписывал этого; перенос пришёл из конфликта stub-env с integration. Подтверждаем как окончательную раскладку или делаем по-другому (например, общий conftest с `pytestmark`-фильтром)?
2. **`subprocess` vs in-process alembic** в integration-тестах — выбрал subprocess для соответствия `make migrate`. Поменять на in-process для скорости?
3. **Lazy `engine` в `db.py`** — нужно или нет? Сейчас module-level constant.
4. **`python-dotenv` в dev-deps** — нужен ли явный пакет вместо моего мини-loader'а в test_migrations.py?
5. **`integration` job не делает teardown postgres** — service-container уничтожается с runner'ом. Если когда-то добавим тесты, которые портят БД безвозвратно (например, тяжёлые операции которые требуют resync) — стоит добавить `if: always()` cleanup-шаг. На текущем сэте 4 теста с `downgrade base` в setup — не нужно.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-006: model tweaks (metadata_ NOT NULL, full_name String(128), ck convention) + `src/shared/db.py` (async engine + sessionmaker + get_session) + Alembic с async env.py + `0001_init` миграция (8 таблиц + 24 индекса) + 6 Makefile-целей + новый CI job `integration` (postgres:16 service). 4 интеграционных теста зелёные. PR [#14](https://github.com/nmetluk/bettgbot/pull/14) → squash `fdddac9`. Pre-task cleanup [#13](https://github.com/nmetluk/bettgbot/pull/13).
```

## Метрики

- Файлов добавлено: 8 (db.py, alembic.ini, env.py, script.py.mako, 0001_init.py, migrations/__init__, integration/__init__, test_migrations.py)
- Файлов изменено: 6 (3 модели, Makefile, pyproject, ci.yml)
- Коммитов в PR: 6
- Тестов: 4 integration (22 unit как и было)
- Время на выполнение: ~80 мин (включая cleanup PR, итерации с env.py URL fix, конфликт stub-env, проверка use_alter в upgrade/downgrade)
