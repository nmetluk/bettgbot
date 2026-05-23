---
task: TASK-009
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/23
branch: feature/TASK-009-services
commits:
  - b664b25 refactor(external): apply tweaks from TASK-008 review (shared X-Request-Id, cache factory)
  - 41c6e95 feat(shared): domain exceptions
  - a960862 feat(services): user, event, prediction, reminder, stats, audit
  - 58e9216 test(services): 31 integration tests for happy paths and domain exceptions
  - 60cdbb4 chore(handoff): mark TASK-009 in-progress
---

# Отчёт по TASK-009: Сервисный слой — шесть сервисов + доменные исключения

## Сводка

В репо собран полный «средний этаж» архитектуры. `src/shared/exceptions.py` — иерархия с корнем `DomainError` и 13 подклассами, разделёнными по доменам (регистрация / прогноз / админ-события / напоминания). `src/shared/services/` — шесть сервисов: `UserService`, `EventService`, `PredictionService`, `ReminderService`, `StatsService`, `AuditService`. Каждый берёт `AsyncSession` в конструкторе и создаёт внутри нужные репозитории; `UserService` дополнительно принимает `ExternalUserRegistryClient` для DI mock'а в тестах. Все write-методы делают `await self._session.commit()` в конце успешного пути; домен-исключения коммит не делают.

`EventService.set_result` — единая транзакция: `events.set_result` (event.is_archived, result_outcome_id, archived_at) → `predictions.mark_correctness` (через `update + case`) → `audit.add` → `commit`. Возвращает количество размеченных прогнозов для UX-баннера админки.

`UserService.register_or_authenticate` обрабатывает три случая внешнего реестра: успех (`is_allowed=True` — создаёт `User` + дефолтный `ReminderSetting [1440, 60]`), отказ (`is_allowed=False` → `UserNotAllowed(reason=...)`), сетевой сбой (`ExternalApiError` → `RegistryUnavailableError` с `__cause__`). Существующий пользователь обновляет `last_seen_at` без повторной верификации.

Audit-запись внутри других сервисов делается напрямую через `AuditLogRepository(self._session).add(...)`, не через `AuditService` — это явно зафиксировано в задаче, чтобы не плодить инстансы и не путать транзакционные границы.

31 integration-тест в `tests/integration/services/`. Все они используют `nested_session` fixture (внешняя транзакция + SAVEPOINT) — без неё сервисный `commit()` сохранил бы данные между тестами. Listener `after_transaction_end` на sync-сессии переоткрывает SAVEPOINT после каждого commit'а; в teardown откатывается outer transaction. `UserService`-тесты используют `StubRegistry` — in-memory implementation `ExternalUserRegistryClient` Protocol на ~10 строк.

Step 0 (TASK-008 review tweaks) — отдельный коммит до сервисов: `X-Request-Id` теперь shared между retry'ями одного `verify(phone)`; `get_registry_client` обёрнут в `@lru_cache(maxsize=1)`.

Pre-task cleanup PR [#22](https://github.com/nmetluk/bettgbot/pull/22) свернул правки cowork (5 новых DECISIONS, sessions/2026-05-23-07).

## Изменённые файлы

```
* src/shared/external/http_registry.py   # X-Request-Id вынесен из retry loop
* src/shared/external/__init__.py        # @lru_cache на get_registry_client
+ src/shared/exceptions.py               # 13 классов под DomainError
+ src/shared/services/__init__.py        # re-export 6 сервисов
+ src/shared/services/user.py
+ src/shared/services/event.py
+ src/shared/services/prediction.py
+ src/shared/services/reminder.py
+ src/shared/services/stats.py
+ src/shared/services/audit.py
+ tests/integration/services/__init__.py
+ tests/integration/services/conftest.py # nested_session + StubRegistry
+ tests/integration/services/test_user_service.py        # 7
+ tests/integration/services/test_event_service.py       # 7
+ tests/integration/services/test_prediction_service.py  # 7
+ tests/integration/services/test_reminder_service.py    # 4
+ tests/integration/services/test_stats_service.py       # 2
+ tests/integration/services/test_audit_service.py       # 3
* tests/unit/external/test_factory.py    # +cache_clear() для get_registry_client
* handoff/inbox/TASK-009-services.md → in-progress → archive
+ handoff/archive/TASK-009-services/task.md
+ handoff/outbox/TASK-009-report.md
```

## Тесты и CI

```
Локально:
  ruff check src tests             All checks passed!
  ruff format --check src tests    71 files already formatted
  mypy src/shared (strict)         Success: no issues found in 35 source files
  pytest                           109 passed in 8.33s

CI PR #23 (все четыре job'а зелёные):
  Lint (ruff)                      11s
  Typecheck (mypy)                 16s
  Tests (pytest, unit)             12s
  Integration (alembic on real postgres)  50s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
make up && make migrate

uv run pytest tests/unit -m "not integration" -v   # 41
uv run pytest tests/integration -m integration -v  # 68 (4 migrations + 33 repos + 31 services)
```

## Что не сделано / вынесено

1. **`CategoryService`, `OutcomeService` отдельный класс, `AdminAuthService`** — TASK-019+. `EventService` инкапсулирует CRUD outcome'ов.
2. **Pre-validation `predictions_close_at <= starts_at`** в `EventService.create_event` оставлен на DB CHECK — сервис не дублирует. Если хочется доменное исключение раньше — добавим `EventValidationError`.
3. **DI-фреймворки** не подключены — простая инъекция через конструктор.

## Открытые вопросы для проектировщика

1. **Соглашение `from ..external.registry import ...` vs `from ..external import ...`.** В `UserService` импортирую тип `ExternalUserRegistryClient` из `..external.registry`, а не из пакета — последний при импорте дёрнет фабрику. Это значимый паттерн для всех будущих сервисов; стоит ли зафиксировать в `docs/08-conventions.md`?
2. **Унификация `session` / `nested_session` fixtures.** Сейчас repository-тесты используют простой `session` с rollback, service-тесты — `nested_session` с SAVEPOINT. Альтернатива — везде `nested_session` (даже когда не нужно). Это снимет mental overhead, но добавит чуть-чуть оверхеда per-test.
3. **`SAWarning: transaction already deassociated from connection`** на `test_delete_outcome_in_use_raises`. Сервис вызывает `self._session.rollback()` после IntegrityError, что конфликтует с SAVEPOINT-структурой fixture. Warning безвредный, но шумный. Варианты: (а) убрать `rollback` из сервиса, полагаться на caller; (б) подавить warning в pyproject. Какой подход?
4. **`UserService.touch_last_seen` сам commit'ит.** Если handler вызывает его как часть большего сценария (middleware каждого update), это лишний round-trip. Сделать commit опциональным флагом или оставить?
5. **`StubRegistry` в `tests/integration/services/conftest.py`.** Если унит-тесты с сервисами появятся (например, `UserService.register` с замоканной репозиторий-стороной) — стуб переедет в общий `tests/_stubs.py` или `tests/conftest.py`. Сейчас не нужно.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-009: 6 доменных сервисов в `src/shared/services/` (`UserService`, `EventService`, `PredictionService`, `ReminderService`, `StatsService`, `AuditService`) + `src/shared/exceptions.py` с иерархией `DomainError`. Все write-методы владеют транзакцией (commit в сервисе). `EventService.set_result` — единая транзакция (update + mark + audit). TASK-008 review tweaks (shared X-Request-Id, lru_cache фабрики). 31 integration-тест с `nested_session`-фикстурой (SAVEPOINT для сервисного commit). PR [#23](https://github.com/nmetluk/bettgbot/pull/23) → squash `b102b9e`. Pre-task cleanup [#22](https://github.com/nmetluk/bettgbot/pull/22).
```

## Метрики

- Файлов добавлено: 16 (1 exceptions + 7 services + 8 tests)
- Файлов изменено: 3 (http_registry, external/__init__, test_factory)
- Строк кода: ~470 (services) + ~110 (exceptions) + ~520 (tests)
- Тестов добавлено: 31 (всего теперь 109: 41 unit + 4 migrations + 33 repositories + 31 services)
- Время на выполнение: ~80 мин (включая cleanup PR, фикс CHECK violation в test_event_archived, итерации с nested_session конфигурацией)
