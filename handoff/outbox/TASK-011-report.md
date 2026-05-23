---
task: TASK-011
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/29
branch: feature/TASK-011-start-handler
commits:
  - 232f7a3 feat(bot): inject registry via dp workflow-data
  - 0302f41 feat(texts): add NEED_OWN_CONTACT, ALREADY_REGISTERED, WELCOME_NEW_REGISTERED
  - 9830563 feat(bot): /start handler + contact handler with registration flow
  - 3d8c2ed test(bot): start and contact handler unit tests
  - 10d5f27 chore(handoff): mark TASK-011 in-progress
---

# Отчёт по TASK-011: `/start` + Contact handler — регистрация пользователя

## Сводка

Первый реальный сценарий бота работает: пользователь шлёт `/start` → бот понимает, существует он или нет, и в нужный момент просит контакт → проверяет номер во внешнем реестре (mock в dev) → создаёт `User` с дефолтным `ReminderSetting [1440, 60]` → отвечает «Добро пожаловать» с главным меню. Все edge-cases (чужой контакт, заблокированный пользователь, уже зарегистрирован, `not_found` в реестре, `ExternalApiError`) обрабатываются понятными текстами.

DI registry — через `dp["registry"]`: `build_dispatcher` ставит `dp["registry"] = get_registry_client()`, handler принимает параметр `registry: ExternalUserRegistryClient` — aiogram инжектит из workflow-data по имени. Shutdown через `getattr(...)+callable()` — Mock без `.close()` не ломает finally.

`cmd_start` начинается с `state.clear()` — на случай, если пользователь жмёт `/start` в середине FSM-flow (выбор события в TASK-013, настройка напоминаний в TASK-015).

`on_contact` сначала отсекает рискованные ветки (чужой контакт, blocked, уже зарегистрирован) и только потом вызывает `UserService.register_or_authenticate`. Phone приводится к E.164 (`+71234567890`) — Telegram отдаёт без `+`. Логи структурные с `phone_hash = sha256(phone)[:8]` — PII не светим.

Pre-task cleanup PR [#28](https://github.com/nmetluk/bettgbot/pull/28) свернул правки cowork (новое правило «Фабрики читают свежий конфиг» в `docs/08-conventions.md`, раздел «Технический долг» в BACKLOG).

## Изменённые файлы

```
* src/bot/main.py                              # dp['registry'] + close on shutdown
* src/bot/routers/start.py                     # cmd_start + on_contact + helpers
* src/bot/texts.py                             # +3 константы
* tests/unit/bot/test_main_smoke.py            # +assert dp['registry']
+ tests/unit/bot/routers/__init__.py
+ tests/unit/bot/routers/test_start_handler.py    # 4 теста
+ tests/unit/bot/routers/test_contact_handler.py  # 6 тестов
* handoff/inbox/TASK-011-start-handler.md → in-progress → archive
+ handoff/archive/TASK-011-start-handler/task.md
+ handoff/outbox/TASK-011-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    95 files already formatted
mypy src/shared src/bot          Success: no issues found in 51 source files
pytest                           129 passed in 30.22s

CI PR #29 — все четыре job'а зелёные:
  Lint (ruff)                     12s
  Typecheck (mypy)                15s
  Tests (pytest, unit)            15s
  Integration (alembic on real postgres)  39s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
# Свой TG-токен в TELEGRAM_BOT_TOKEN
# Свой телефон в infra/mock-registry.yml allowed: или в MOCK_REGISTRY_ALLOWED=+7XXX
make up && make migrate
uv run python -m src.bot.main
# В Telegram → /start → share contact → видишь приветствие + меню
```

## Что не сделано / вынесено

1. **Real handler'ы команд** `/events`, `/predict`, `/my`, `/reminders`, `/help` — TASK-012 — TASK-016.
2. **FSM-states** для выбора события / исхода — TASK-013.
3. **Integration-тесты с реальным Telegram API** — DoD это явно запрещает; остались mock-уровневые.
4. **`_phone_hash` дубликат**: одна строка в `start.py` и `http_registry.py`. Если появится 3-е место — вынесу в `src/shared/utils.py`.

## Открытые вопросы для проектировщика

1. **Phone нормализация в handler'е (`_normalize_phone`).** Это форматирование входа. Альтернатива — нормализовать в `UserService.register_or_authenticate`, сервис принимает любой формат. Текущее проще, но дублируется при будущих handler'ах ввода телефона вручную. Перенести в сервис?
2. **`_phone_hash` дубликат.** Helper в `src/shared/utils.py`?
3. **`logger.warning("bot.start.registry_unavailable", ...)`** vs `info`. Я взял warning — деградация внешнего реестра. Согласуем?
4. **`{first_name}` в `WELCOME_NEW_REGISTERED` через `str.format()`**. Если имя содержит фигурную скобку — сломается. На практике редко. Принять/перейти на `replace`?
5. **`on_contact` narrowing-проверка `if message.contact is None or message.from_user is None: return`**. F.contact гарантирует contact; mypy strict требует явный narrow для from_user. Согласуем?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-011: первый реальный handler `/start` + contact в `src/bot/routers/start.py`. DI registry через `dp['registry']` (workflow-data aiogram). Полная цепочка регистрации: `/start` → contact → `UserService.register_or_authenticate` → mock-реестр → `User` + дефолтный `ReminderSetting`. Все ветки edge-cases (чужой контакт, blocked, not_found, ExternalApiError) с понятными текстами. PII (телефон) в логах только sha256[:8]. 10 новых unit-тестов. PR [#29](https://github.com/nmetluk/bettgbot/pull/29) → squash `82e8cc4`. Pre-task cleanup [#28](https://github.com/nmetluk/bettgbot/pull/28).
```

## Метрики

- Файлов добавлено: 3 (2 теста + __init__)
- Файлов изменено: 4 (main, start.py, texts.py, test_main_smoke)
- Строк кода: ~150 (start.py) + ~130 (тесты)
- Тестов добавлено: 10 (всего теперь 129: 60 unit + 4 migrations + 33 repos + 32 services)
- Время на выполнение: ~50 мин (включая cleanup PR, фикс `# type: narrowing` синтаксиса в комментарии, корректное mypy-narrowing для F.contact)
