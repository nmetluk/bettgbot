# Brief — task-010-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-010 и подготовить следующий шаг.

## Контекст

Локальный агент закрыл TASK-010 чисто за шесть коммитов: Step 0 (правки TASK-009) → `src/bot/main.py` с `build_dispatcher()` (testable) → три middleware (logging/session/user) → 6 пустых router-стабов + keyboards/states/texts → `UserService.registry` сделан Optional → 9 unit-тестов. Внутри задачи добавлен **`src/__init__.py`** — без него mypy ругался на канонизацию имён модулей. 119 тестов зелёные, mypy strict зелёный, четыре CI job'а. PR [#26](https://github.com/nmetluk/bettgbot/pull/26) → squash `5224140`. Pre-task cleanup PR [#25](https://github.com/nmetluk/bettgbot/pull/25).

Полный отчёт — [`handoff/outbox/TASK-010-report.md`](../../handoff/outbox/TASK-010-report.md).

## Что сделано в этой сессии

- Приняты решения по пяти открытым вопросам — все формализованы в [`state/DECISIONS.md`](../../state/DECISIONS.md):
  - **Change:** дописана секция «`src/` — полноценный пакет, не namespace» и новая секция «Фабрики читают свежий конфиг» в [`docs/08-conventions.md`](../../docs/08-conventions.md). Первая фиксирует, что все импорты в репо — абсолютные `from src.*`; вторая — что `build_dispatcher`, `get_registry_client` и подобные используют `get_settings()`, не module-level `settings`.
  - **Keep + BACKLOG:** добавлен раздел «Технический долг» в [`state/BACKLOG.md`](../../state/BACKLOG.md) с тремя строками (throttling `touch_last_seen`, HTTP-date в `Retry-After`, `list_with_admin` в AuditLog).
  - **Keep:** `structlog.contextvars` clear в finally — корректное поведение.
  - **Keep:** `TELEGRAM_BOT_TOKEN = "111111:stub-token"` в test conftest — стабильная test-fixture.
- Обновлён [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (закрытие TASK-010, новые шаги TASK-011 → TASK-012 → TASK-013).
- Сформирована задача [`handoff/inbox/TASK-011-start-handler.md`](../../handoff/inbox/TASK-011-start-handler.md) — первый реальный handler.

## Что не сделано / отложено

- **Throttling `touch_last_seen`** — в BACKLOG как тех-долг, реализация триггерится метриками нагрузки.
- **Реальный bot-handler** — это TASK-011 и далее; TASK-010 был только bootstrap.

## Следующие шаги

1. Владелец запускает локальный Claude Code на TASK-011.
2. Локальный агент делает pre-task cleanup PR (правки этой сессии: `docs/08-conventions.md`, BACKLOG, state, новая сессия), мёрджит, потом начинает TASK-011.
3. После TASK-011 — TASK-012 (команда «Все события»).
