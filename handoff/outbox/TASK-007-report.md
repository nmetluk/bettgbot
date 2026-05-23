---
task: TASK-007
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/17
branch: feature/TASK-007-repositories
commits:
  - ddd8735 feat(repositories): 8 thin query-layer repositories
  - 3f67073 test(repositories): 37 integration tests + shared conftest
  - b80513f chore(handoff): mark TASK-007 in-progress
  - ac53312 fix(ci): narrow unit test job to tests/unit/
---

# Отчёт по TASK-007: Репозитории — тонкий query-слой над агрегатами

## Сводка

В `src/shared/repositories/` теперь восемь классов, по одному на каждую модель: `UserRepository`, `CategoryRepository`, `EventRepository`, `OutcomeRepository`, `PredictionRepository`, `ReminderSettingRepository`, `AdminUserRepository`, `AuditLogRepository`. Все по единому шаблону: `AsyncSession` в конструкторе, никакой бизнес-логики, никакого `commit/rollback`, eager-loading через явный `selectinload(...)`, возвраты `Sequence[T]`. Объём методов жёстко по DoD — ничего «на потом».

`PredictionRepository` и `ReminderSettingRepository` используют `pg_insert(...).on_conflict_do_update(...).returning(*)` для upsert, после которого вызывают `session.refresh(obj)` — иначе identity_map возвращает закэшированный экземпляр со старыми значениями. `PredictionRepository.mark_correctness` — один UPDATE с `case(...)` на всех прогнозах события. `PredictionRepository.users_without_prediction_for_event` — `NOT EXISTS`-подзапрос с фильтром на `User.is_blocked`. `ReminderSettingRepository.list_eligible_user_ids` — pure-SQL `:offset = ANY(reminder_setting.offsets_minutes)` через `text+bindparam`, потому что ORM-формы `column.any_()` / `contains()` mypy strict не понимает.

37 integration-тестов в `tests/integration/repositories/`. Общая infra — в `tests/integration/conftest.py`: загрузка `.env` (для локального запуска), session-scope `alembic upgrade head` перед всем, helper-фабрики `make_admin/category/user/event/outcome` (counter + uuid для уникальности), фикстура `session` с **per-test engine + NullPool**. Per-test engine нужен потому что `src.shared.db.engine` — module-level singleton, привязанный к первому event loop'у, а pytest-asyncio даёт каждому тесту свой loop — на втором тесте получаем `RuntimeError: Event loop is closed`. NullPool гарантирует, что каждое соединение свежее.

В CI пришлось сузить unit job до `tests/unit/`: pytest при collection импортирует все файлы из `testpaths`, включая `tests/integration/repositories/test_*.py`, которые тянут `from src.shared.repositories import ...` → `src.shared.config` → `settings = get_settings()` — без stub-env (он живёт только в `tests/unit/conftest.py`) это падает на `AdminSettings.secret_key`. Workflow-фикс — четвёртый коммит PR.

Pre-task cleanup PR [#16](https://github.com/nmetluk/bettgbot/pull/16) свёл правки cowork (BACKLOG renumber, 6 новых DECISIONS, sessions/2026-05-23-05).

## Изменённые файлы

```
+ src/shared/repositories/__init__.py            # re-export 8 классов
+ src/shared/repositories/user.py
+ src/shared/repositories/category.py
+ src/shared/repositories/event.py
+ src/shared/repositories/outcome.py
+ src/shared/repositories/prediction.py
+ src/shared/repositories/reminder_setting.py
+ src/shared/repositories/admin_user.py
+ src/shared/repositories/audit_log.py
+ tests/integration/conftest.py                  # _load_dotenv, migrations, session+NullPool, фабрики
+ tests/integration/repositories/__init__.py
+ tests/integration/repositories/test_user_repository.py            # 6
+ tests/integration/repositories/test_category_repository.py        # 5
+ tests/integration/repositories/test_event_repository.py           # 6
+ tests/integration/repositories/test_outcome_repository.py         # 3
+ tests/integration/repositories/test_prediction_repository.py      # 5
+ tests/integration/repositories/test_reminder_setting_repository.py # 2
+ tests/integration/repositories/test_admin_user_repository.py      # 3
+ tests/integration/repositories/test_audit_log_repository.py       # 3
* tests/integration/test_migrations.py           # fresh_db teardown → upgrade head
* .github/workflows/ci.yml                       # unit job: только tests/unit
* handoff/inbox/TASK-007-repositories.md → in-progress → archive
+ handoff/archive/TASK-007-repositories/task.md
+ handoff/outbox/TASK-007-report.md
```

## Тесты и CI

```
Локально:
  ruff check src tests              All checks passed!
  ruff format --check src tests     47 files already formatted
  mypy src/shared (strict)          Success: no issues found in 23 source files
  pytest                            59 passed in 8.78s
    - 22 unit
    - 37 integration:
      - 4 migrations
      - 6+5+6+3+5+2+3+3 = 33 repositories

CI PR #17 — все четыре job'а зелёные (после fix ac53312):
  Lint (ruff)                       9s
  Typecheck (mypy)                  14s
  Tests (pytest, unit)              10s
  Integration (alembic on real postgres)  38s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env

make up
make migrate

# unit
uv run pytest tests/unit -m "not integration" -v

# integration (compose должен быть up)
uv run pytest tests/integration -m integration -v
```

## Что не сделано / вынесено

1. **Сервисы (`UserService`, `EventService`, …)** — TASK-008+.
2. **Базовый `BaseRepository[T]`** не вводил: профили методов разные у каждого репозитория, общего слишком мало, чтобы оправдать generic-обёртку.
3. **Дополнительные методы** не добавлены молча. Если что-то понадобится в TASK-008 — добавим в той задаче.
4. **factory-boy** не используется — `make_*` helper-функции с counter и uuid справляются без overhead.

## Открытые вопросы для проектировщика

1. **Per-test engine с `NullPool` в integration-conftest.** Альтернативы: (а) переключить pytest-asyncio на `asyncio_default_fixture_loop_scope = "session"` — общий loop, но другие side-эффекты возможны; (б) сделать `src.shared.db.engine` ленивым/per-loop; (в) текущий — per-test engine + NullPool. Текущий чистый и изолированный, но имеет накладной расход на создание engine ~1мс/тест. Какой вариант формализовать?
2. **`refresh` после `upsert`.** В `PredictionRepository` и `ReminderSettingRepository` после `RETURNING *` делаем явный `session.refresh(obj)` чтобы обойти identity_map. Альтернатива — `session.expire(obj, ["only-the-changing-fields"])` — экономия одного round-trip. Сейчас не делал.
3. **Сужение unit job до `tests/unit`** в CI workflow. Альтернатива — расширить workflow `env:` блок stub-значениями и для unit job (так же как для integration job). Это позволит `pytest tests` без указания директории. Какой вариант предпочтительнее?
4. **`Event.metadata_` default в `EventRepository.create()`.** Сейчас репозиторий ставит `{}` если передали `None` — server_default тоже работает, дублирование подстраховочное. Убрать?
5. **`AuditLogRepository.list` без `selectinload(admin)`.** Если шаблон админки рисует `entry.admin.full_name`, без подгрузки получим IO в context'е после закрытия сессии. Добавлять метод `list_with_admin` сейчас или в TASK-008 (когда появится сервис админки и точно станет ясно)?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-007: 8 репозиториев в `src/shared/repositories/` — тонкий query-слой (`AsyncSession` в конструкторе, без бизнес-логики, без commit). `pg_insert(...).on_conflict_do_update` для upsert, `mark_correctness` через `update+case`, partial-index использован в `list_eligible_user_ids`. 37 integration-тестов на реальный Postgres (общий conftest с per-test engine+NullPool — обход «Event loop is closed»). PR [#17](https://github.com/nmetluk/bettgbot/pull/17) → squash `6815666`. Pre-task cleanup [#16](https://github.com/nmetluk/bettgbot/pull/16).
```

## Метрики

- Файлов добавлено: 18 (9 репозиториев+__init__, 9 тестов+__init__+conftest)
- Файлов изменено: 2 (test_migrations.py, ci.yml)
- Строк кода: ~750 (repositories) + ~600 (tests + conftest)
- Тестов добавлено: 33 (всего теперь 59: 22 unit + 4 migrations + 33 repositories)
- Время на выполнение: ~80 мин (включая cleanup PR, итерации с mypy на ARRAY.any() / `column.contains()`, фикс event-loop через NullPool, фикс CI collection)
