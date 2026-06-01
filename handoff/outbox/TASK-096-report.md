---
task: TASK-096
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/190
branch: (squash-merged, ветка удалена)
commits:
  - 45e5ab2 chore: remove external user registry (TASK-096 open registration) (#190)
---

# Отчёт по TASK-096: Открытая регистрация — удалить внешний реестр проверки пользователей

> ⚠️ **Отчёт оформлен cowork-агентом post-factum.** Код был реализован и
> смёрджен (PR #190), но исполнитель не закрыл задачу по протоколу: не
> написал отчёт, не переместил задачу `inbox → archive`. Cowork-агент
> восстановил handoff-гигиену (этот отчёт + архивация) и сверил факт
> изменений против `origin/main`, а не по словам. См. запись в
> [`state/DECISIONS.md`](../../state/DECISIONS.md) о дрейфе handoff-закрытия.

## Сводка

Внешний реестр проверки пользователей удалён полностью (вариант «удалить», ADR-0006). Регистрация стала открытой: `UserService.register_or_authenticate` создаёт пользователя сразу после получения **своего** контакта, без вызова внешнего API; единственный отказной путь — `is_blocked`.

Проверено по `origin/main` (коммит `45e5ab2`, после `git pull`):

- `src/shared/external/` удалён из git целиком (нет файлов в `git ls-files`).
- Живых ссылок на реестр в `.py` (src и tests) нет; переменных `EXTERNAL_*`/`MOCK_REGISTRY_*` в `infra/` нет.
- `register_or_authenticate` без параметра `registry`; `start.py:on_contact` без `UserNotAllowed`/`RegistryUnavailableError`. `_phone_hash` оставлен осознанно — используется для логирования регистрации.
- `main.py`, `config.py` чисты от обвязки реестра; `UserNotAllowed`/`RegistryUnavailableError` удалены, **`UserBlockedError` сохранён**; тексты `PHONE_NOT_FOUND`/`REGISTRY_UNAVAILABLE` удалены, `NEED_OWN_CONTACT` на месте; `infra/mock-registry.yml` удалён.
- Схема БД не менялась (миграций нет) — как и требовалось.

PR #190 прошёл auto-merge, значит все required-чеки (lint, typecheck, unit-test, integration, handoff-consistency) были зелёными.

## Изменённые файлы

```
- src/shared/external/{__init__,registry,http_registry,mock_registry}.py   # удалены (-444)
- infra/mock-registry.yml                                                  # удалён
- tests/unit/external/{__init__,test_factory,test_http_registry,test_mock_registry}.py  # удалены (-333)
* src/shared/services/user.py        # убран registry из register_or_authenticate
* src/bot/routers/start.py           # упрощён on_contact (-56/+...)
* src/bot/main.py                    # убрана DI-проводка registry
* src/shared/config.py               # удалён ExternalRegistrySettings + prod-валидация (-70)
* src/shared/exceptions.py           # удалены UserNotAllowed, RegistryUnavailableError
* src/bot/texts.py                   # удалены PHONE_NOT_FOUND, REGISTRY_UNAVAILABLE
* src/shared/__init__.py, src/bot/middlewares/user.py, src/admin/routes/users.py  # чистка импортов
* infra/.env.example, .env.bot.example, .env.prod.example, docker-compose.yml     # убраны env реестра
* tests/integration/services/{conftest,test_user_service}.py  # убран StubRegistry + сценарии not_allowed
* tests/unit/bot/routers/test_contact_handler.py, tests/unit/bot/test_main_smoke.py,
  tests/unit/test_config.py, tests/unit/conftest.py            # адаптированы тесты
```

Итого: 29 файлов, +44 / −1164.

## Как воспроизвести / запустить

```bash
git checkout main && git pull origin main
ruff check . && mypy src/shared
pytest
# Регистрация: /start → поделиться своим контактом → пользователь создаётся сразу.
```

## Что не сделано

Ничего из скоупа задачи не вынесено. Подчищен только локальный stale-артефакт `src/shared/external/__pycache__/` (не был в git).

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-06-01 — TASK-096: открытая регистрация, внешний реестр проверки пользователей удалён полностью (ADR-0006, PR #190)
```

## Метрики

- Удалено ~1164 строк, добавлено ~44.
- Файлов затронуто: 29 (7 удалено).
