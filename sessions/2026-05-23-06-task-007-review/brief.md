# Brief — task-007-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-007 и подготовить следующий шаг.

## Контекст

Локальный агент закрыл TASK-007 чисто за четыре коммита: 8 репозиториев в `src/shared/repositories/` (~750 строк), общий `tests/integration/conftest.py` с per-test engine + NullPool и helper-фабриками (`make_admin/category/user/event/outcome`), 33 integration-теста на реальный Postgres (плюс старые 22 unit + 4 migrations = 59 всего). mypy strict зелёный, все четыре CI job'а зелёные. PR [#17](https://github.com/nmetluk/bettgbot/pull/17) → squash `6815666`. Pre-task cleanup PR [#16](https://github.com/nmetluk/bettgbot/pull/16).

Внутри задачи всплыли две неочевидные проблемы, обе решены на месте:

1. `src.shared.db.engine` — module-level singleton, привязан к первому event loop'у; pytest-asyncio даёт каждому тесту свой loop → `RuntimeError: Event loop is closed`. Решение: per-test engine с NullPool.
2. CI unit job ругался на коллекцию integration-тестов (импорт `src.shared.repositories` → `Settings()` без stub-env). Решение: сузить unit job до `tests/unit/` явно (фикс-коммит `ac53312`).

Полный отчёт — [`handoff/outbox/TASK-007-report.md`](../../handoff/outbox/TASK-007-report.md).

## Что сделано в этой сессии

- Приняты решения по пяти открытым вопросам review — все «оставить как есть», формализованы в [`state/DECISIONS.md`](../../state/DECISIONS.md):
  - per-test engine с NullPool;
  - `session.refresh(obj)` после `pg_insert + on_conflict_do_update`;
  - сужение CI unit job до `tests/unit/`;
  - `EventRepository.create()` ставит `metadata_={}` для удобства in-memory объекта;
  - `AuditLogRepository.list_with_admin` отложен до TASK-026.
- Принято **архитектурное решение** о перестановке TASK-008 и TASK-009: внешний registry идёт **до** сервисов, потому что `UserService.register_or_authenticate` зависит от `ExternalUserRegistryClient.verify(phone)`. [`state/BACKLOG.md`](../../state/BACKLOG.md) обновлён.
- Обновлён [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (закрытие TASK-007, новые следующие шаги).
- Сформирована задача [`handoff/inbox/TASK-008-external-registry.md`](../../handoff/inbox/TASK-008-external-registry.md).

## Что не сделано / отложено

- **`list_with_admin` в AuditLogRepository** — добавим в TASK-026 (admin audit UI), когда станет ясен реальный pattern доступа.
- **Сервисы** теперь TASK-009 (а не TASK-008, как раньше планировалось).

## Следующие шаги

1. Владелец запускает локальный Claude Code на TASK-008.
2. Локальный агент сначала делает pre-task cleanup PR (правки этой сессии: state-файлы, BACKLOG, новая сессия), мёрджит, потом начинает TASK-008.
3. После TASK-008 — TASK-009 (все шесть сервисов, включая `UserService` с инъекцией registry-клиента).
