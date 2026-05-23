# Brief — task-011-review

**Дата:** 2026-05-23
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-011 и подготовить следующий шаг.

## Контекст

Локальный агент закрыл TASK-011 чисто за пять коммитов: Step 1 (`dp["registry"]` workflow-data) → texts (3 константы) → handlers (`cmd_start` + `on_contact`) → unit-тесты (10) → archive. После TASK-011 бот делает первый полезный сценарий end-to-end: `/start` → share contact → проверка через mock-реестр → создание `User` + дефолтных `ReminderSetting [1440, 60]` → главное меню. 129 тестов, mypy strict, четыре CI job'а зелёных. PR [#29](https://github.com/nmetluk/bettgbot/pull/29) → squash `82e8cc4`. Pre-task cleanup PR [#28](https://github.com/nmetluk/bettgbot/pull/28).

Полный отчёт — [`handoff/outbox/TASK-011-report.md`](../../handoff/outbox/TASK-011-report.md).

## Что сделано в этой сессии

- Приняты решения по пяти открытым вопросам — все **«keep»**, формализованы в [`state/DECISIONS.md`](../../state/DECISIONS.md):
  - Phone-нормализация в handler'е (граница ввода — handler, сервис принимает только E.164).
  - `_phone_hash` дубликат оставлен до 3-го места использования (правило тройки).
  - `warning` для `RegistryUnavailableError` (деградация внешнего сервиса — сигнал оператору).
  - `str.format()` в `WELCOME_NEW_REGISTERED` — теоретическая уязвимость к `{` отвергается (Telegram не пропускает в имени), i18n-friendly стиль важнее.
  - `if message.contact is None or message.from_user is None: return` — стандартный mypy-narrowing для aiogram-фильтров.
- Обновлён [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md) (закрытие TASK-011, новые шаги TASK-012 → TASK-013 → TASK-014).
- Сформирована задача [`handoff/inbox/TASK-012-events-handler.md`](../../handoff/inbox/TASK-012-events-handler.md) — первая «крупная» handler-задача с inline-клавиатурами и пагинацией.

## Что не сделано / отложено

- **`src/shared/utils.py`** не создаём (правило тройки для `_phone_hash`).
- **«Сделать прогноз» button в карточке события** — оставим без активного callback'а в TASK-012; подключим в TASK-013.

## Следующие шаги

1. Владелец запускает локальный Claude Code на TASK-012.
2. Локальный агент делает pre-task cleanup PR (правки этой сессии: state-файлы, новая сессия), мёрджит, потом начинает TASK-012.
3. После TASK-012 — TASK-013 (FSM «Сделать прогноз»).
