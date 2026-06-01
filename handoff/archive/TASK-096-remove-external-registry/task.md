---
id: TASK-096
created: 2026-06-01
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/adr/0006-open-registration.md
  - docs/06-external-api.md
  - docs/04-bot-flows.md
  - docs/03-data-model.md
  - state/DECISIONS.md
priority: high
estimate: M
---

# TASK-096: Открытая регистрация — удалить внешний реестр проверки пользователей

## Контекст

Заказчик отменил проверку номера по внешнему реестру перед регистрацией (изменение требования 2026-06-01). Регистрация теперь **открытая**: любой, кто поделился **своим** контактом, регистрируется. Единственный отказной путь — `is_blocked = true` (блокировка из админки).

Решение зафиксировано в [ADR-0006](../../docs/adr/0006-open-registration.md) и строке от 2026-06-01 в [`state/DECISIONS.md`](../../state/DECISIONS.md). Спеки уже обновлены проектировщиком: [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) (флоу регистрации), [`docs/03-data-model.md`](../../docs/03-data-model.md) (сущность `User`), [`docs/06-external-api.md`](../../docs/06-external-api.md) помечена SUPERSEDED.

Выбор владельца из вариантов «удалить / отключить / спрятать за флагом» — **полностью удалить** код реестра. Схему БД **не трогаем**: `external_user_id`/`display_name` никогда не сохранялись в `users`, миграции не нужны.

## Цель

Убрать из кодовой базы весь внешний реестр и связанную обвязку; `UserService.register_or_authenticate` создаёт пользователя без вызова внешнего API; бот регистрирует любого, кто прислал свой контакт (кроме заблокированных). Все тесты, линт и типы зелёные.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` коммитом — ОБЯЗАТЕЛЬНО написать
> `handoff/outbox/TASK-096-report.md`.** Без отчёта CI handoff-consistency
> красный, PR не мёрджится. Шаблон — `handoff/templates/report.md`.

- [ ] **`UserService.register_or_authenticate`** (`src/shared/services/user.py`): убран параметр `registry` и вся ветка `verify`/`is_allowed`. Метод создаёт пользователя + default reminder_setting сразу после проверки «нет существующего». Убраны импорты `ExternalApiError`, `ExternalUserRegistryClient`, `RegistryUnavailableError`, `UserNotAllowed`. Конструктор `UserService.__init__` больше не принимает `registry`.
- [ ] **`src/bot/routers/start.py`** (`on_contact`): убран параметр `registry` и `try/except UserNotAllowed/RegistryUnavailableError`. Остаётся: проверка `is_blocked`, проверка «свой контакт» (`contact.user_id == from_user.id`), «уже зарегистрирован», создание пользователя, приветствие. Убраны импорты удалённых исключений и `ExternalUserRegistryClient`. Docstring модуля обновлён (без упоминания внешнего реестра).
- [ ] **`src/bot/main.py`**: удалены `from src.shared.external import get_registry_client`, `dp["registry"] = get_registry_client()` (стр. ~54) и shutdown-хук `dp["registry"].close` (стр. ~86).
- [ ] **`src/shared/external/`** удалён целиком (`registry.py`, `http_registry.py`, `mock_registry.py`, `__init__.py`).
- [ ] **`src/shared/exceptions.py`**: удалены классы `UserNotAllowed`, `RegistryUnavailableError` и их записи в `__all__`. **`UserBlockedError` оставить** — это наш собственный флаг `is_blocked`, не реестр.
- [ ] **`src/bot/texts.py`**: удалены `PHONE_NOT_FOUND`, `REGISTRY_UNAVAILABLE` (и из `__all__`). Проверить, что `NEED_OWN_CONTACT`, `ALREADY_REGISTERED`, `ACCESS_DENIED`, `WELCOME_*` остаются.
- [ ] **`src/shared/config.py`**: удалён класс `ExternalRegistrySettings`, поле `external_registry` в `Settings`, и относящаяся к нему prod-валидация (`external_registry.backend == "mock"` → error). Проверить, что комментарий про плоскую схему env не ссылается на удалённые `EXTERNAL_API_*`/`MOCK_REGISTRY_*` (поправить).
- [ ] **env-примеры**: удалены `EXTERNAL_REGISTRY_BACKEND`, `EXTERNAL_API_*`, `MOCK_REGISTRY_*` из `infra/.env.example`, `infra/.env.bot.example`, `infra/.env.prod.example`, `infra/docker-compose.yml`. Удалён файл `infra/mock-registry.yml`.
- [ ] **Тесты**: удалена директория `tests/unit/external/` целиком. Из `tests/integration/services/conftest.py` и `test_user_service.py` убран `StubRegistry` и сценарии not_allowed/unavailable; оставлены/адаптированы тесты успешной регистрации и «уже существует». `tests/unit/bot/routers/test_contact_handler.py` — убраны кейсы про реестр, добавлен кейс «новый контакт → пользователь создан без реестра». `tests/unit/bot/test_main_smoke.py` — убрана проверка `dp["registry"]`. `tests/unit/test_config.py` — убраны кейсы про `external_registry`/prod-валидацию backend. `tests/unit/admin/test_security_headers.py` и `test_users_handler.py` — проверить, что упоминания только косвенные, поправить при необходимости.
- [ ] `ruff check` чисто, `mypy src/shared` чисто, `pytest` зелёный.
- [ ] PR открыт в GitHub, имя `TASK-096: открытая регистрация — удалить внешний реестр`.
- [ ] Отчёт в `handoff/outbox/TASK-096-report.md` написан.
- [ ] **🚨 Move-семантика inbox→archive:** перед `chore(handoff): archive TASK-096 ...` выполнить `ls handoff/inbox/ | grep TASK-096` — если найдено, `git rm` обе копии (`TASK-096-remove-external-registry.md` И `TASK-096.in-progress.md`). В archive — одна копия.

## Артефакты

- `- src/shared/external/` — удалить директорию целиком
- `- infra/mock-registry.yml` — удалить
- `* src/shared/services/user.py` — упростить `register_or_authenticate`, убрать `registry`
- `* src/bot/routers/start.py` — упростить `on_contact`
- `* src/bot/main.py` — убрать DI-проводку реестра
- `* src/shared/exceptions.py` — удалить `UserNotAllowed`, `RegistryUnavailableError`
- `* src/bot/texts.py` — удалить `PHONE_NOT_FOUND`, `REGISTRY_UNAVAILABLE`
- `* src/shared/config.py` — удалить `ExternalRegistrySettings` + поле + prod-валидацию
- `* infra/.env.example, .env.bot.example, .env.prod.example, docker-compose.yml` — убрать env-переменные реестра
- `* tests/...` — см. DoD (удалить `tests/unit/external/`, адаптировать остальные)

## Ссылки

- Решение: [`docs/adr/0006-open-registration.md`](../../docs/adr/0006-open-registration.md)
- Флоу: [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) (раздел «Регистрация»)
- Модель: [`docs/03-data-model.md`](../../docs/03-data-model.md) (сущность `User`)
- Журнал: [`state/DECISIONS.md`](../../state/DECISIONS.md) (строка 2026-06-01)

## Подсказки исполнителю

- **Грепни перед закрытием**: `grep -rn "external\|registry\|Registry\|UserNotAllowed\|RegistryUnavailable\|ExternalApi\|MOCK_REGISTRY\|EXTERNAL_" src/ tests/ infra/` — не должно остаться живых ссылок (кроме `docs/06`, которая намеренно сохранена как историческая).
- `UserBlockedError` ≠ `UserNotAllowed`: первый — наш `is_blocked`, оставить.
- Ряд DECISIONS-записей от 2026-05-23 относится к удаляемому коду (singleton `get_registry_client`, `_phone_hash` дублирование, `X-Request-Id` и т. п.) — они отменены ADR-0006, чинить их не нужно, просто удаляешь код.
- `_phone_hash` в `start.py` после удаления `http_registry.py` больше нигде не дублируется; если он там не используется в упрощённом `on_contact` (для логов) — убрать вместе с импортом `hashlib`.
- `docs/`, `state/`, `README.md` уже обновлены проектировщиком — **не трогай** их (зона cowork-агента).
