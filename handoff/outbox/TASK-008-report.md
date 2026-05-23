---
task: TASK-008
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/20
branch: feature/TASK-008-external-registry
commits:
  - f679f87 feat(external): registry interface + mock + http clients + factory
  - b5ff0be test(external): 19 unit tests for mock + http + factory
  - f75bd07 chore(handoff): mark TASK-008 in-progress
---

# Отчёт по TASK-008: Внешний реестр пользователей — интерфейс + mock + HTTP-каркас

## Сводка

В `src/shared/external/` собран полный комплект для единственной внешней интеграции проекта. `registry.py` определяет общие типы — `VerificationResult` (frozen dataclass с `is_allowed/external_user_id/display_name/reason`), `ExternalUserRegistryClient` (`@runtime_checkable` Protocol с одним `async def verify(phone)`), `ExternalApiError` (с опциональным `cause`). На этот контракт будут опираться сервисы в TASK-009+.

`MockExternalUserRegistryClient` загружает конфиг из YAML (по эталону `infra/mock-registry.yml`) и/или env CSV (`MOCK_REGISTRY_ALLOWED`). CSV перекрывает `allowed` из файла; `blocked` и `simulate` (`latency_ms`, `fail_rate`) — только из YAML. Внутри клиента — `random.random() < fail_rate` для симуляции сбоя, `asyncio.sleep(latency_ms / 1000)` для имитации сети. Парсер `load_mock_config` defensive: пустой/невалидный YAML → пустой конфиг (см. открытые вопросы).

`HttpExternalUserRegistryClient` — на `httpx.AsyncClient` с retry-политикой по `docs/06-external-api.md`: 5xx и сетевые ошибки → 2 ретрая с backoff `[0.5s, 1.0s]`, 429 → 1 ретрай с `Retry-After` (только секунды), 401 и прочие 4xx — не ретраим. На каждый запрос: `Authorization: Bearer <token>`, `X-Request-Id: uuid4().hex` (свежий, см. открытый вопрос #1), тело `{"phone": ...}`. Логи структурные через `structlog` — `external_api.{endpoint,phone_hash,status_code,latency_ms,retry_count,outcome}`; телефон хешируется sha256[:8]. `sleep` callable подменяется через конструктор — тесты retry-логики бегут без реальных задержек.

`get_registry_client()` (фабрика) использует `get_settings()` (не module-level `settings`), чтобы тесты с `monkeypatch.setenv + cache_clear` видели свежие значения backend/url/token. На каждый вызов — новый клиент, без кэширования (см. открытый вопрос #3).

Pre-task cleanup PR [#19](https://github.com/nmetluk/bettgbot/pull/19) свернул правки cowork (BACKLOG renumber, 6 новых DECISIONS, sessions/2026-05-23-06).

## Изменённые файлы

```
+ src/shared/external/__init__.py            # фабрика + re-export 7 символов
+ src/shared/external/registry.py            # VerificationResult, Protocol, ExternalApiError
+ src/shared/external/mock_registry.py       # Mock client + load_mock_config
+ src/shared/external/http_registry.py       # Http client с retry/backoff/logging
+ tests/unit/external/__init__.py
+ tests/unit/external/test_mock_registry.py  # 7 тестов
+ tests/unit/external/test_http_registry.py  # 10 тестов
+ tests/unit/external/test_factory.py        # 2 теста (mock vs http по env)
* handoff/inbox/TASK-008-external-registry.md → in-progress → archive
+ handoff/archive/TASK-008-external-registry/task.md
+ handoff/outbox/TASK-008-report.md
```

## Тесты и CI

```
Локально:
  ruff check src tests              All checks passed!
  ruff format --check src tests     55 files already formatted
  mypy src/shared (strict)          Success: no issues found in 27 source files
  pytest                            78 passed in 6.99s
    - 22 base unit (config/logging/smoke)
    - 19 external (7 mock + 10 http + 2 factory)
    - 4 migrations
    - 33 repositories

CI PR #20 — все четыре job'а зелёные:
  Lint (ruff)                       8s
  Typecheck (mypy)                  15s
  Tests (pytest, unit)              13s
  Integration (alembic on real postgres)  38s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env  # EXTERNAL_REGISTRY_BACKEND=mock по умолчанию

uv run pytest tests/unit/external -v   # 19 тестов

# Демо mock:
uv run python -c "
import asyncio
from src.shared.external import get_registry_client
async def main():
    client = get_registry_client()
    print(await client.verify('+71111111111'))  # allowed (если файл подключён)
    print(await client.verify('+700'))           # not_found
asyncio.run(main())
"
```

## Что не сделано / вынесено

1. **`UserService.register_or_authenticate`** интеграция — TASK-009.
2. **`Retry-After` HTTP-date** не парсится. По спеке достаточно секунд.
3. **`tenacity` / `pytest-httpx` / `responses`** не подключены — обходимся ручной retry-логикой и `httpx.MockTransport`.
4. **Метрики (счётчики/гистограммы) на будущее** — не добавлены, в DoD это явно про MVP.

## Открытые вопросы для проектировщика

1. **`X-Request-Id` на retry**. Сейчас каждая попытка получает свежий uuid — так в логах видно отдельные попытки, плюс retry_count. Подсказка в задаче говорила обратное: «при ретрае тот же запрос имеет тот же ID для tracing». Я отступил от этого, потому что (а) для tracing достаточно глобального correlation_id (его пробросит middleware aiogram/FastAPI), (б) явные ID попыток дают точное соответствие лог-строк HTTP-логам. Меняем на shared ID или ОК?
2. **`get_registry_client()` не кэширует.** Каждый вызов делает новый `httpx.AsyncClient` → новый connection pool. В DI (TASK-009) скорее всего захотим singleton через `lru_cache` (или передавать клиент явно как dependency). Сейчас «не кэшировать преждевременно» — норм или сразу `lru_cache`?
3. **`load_mock_config` defensive parsing.** Невалидный YAML структурно (`allowed: "foo"`) → пустой `MockConfig`. Альтернатива — `pydantic.BaseModel` парсер с явной ошибкой при невалидном формате. Не делал, потому что YAML — dev-инфра, не пользовательский ввод. Согласуем?
4. **`MockExternalUserRegistryClient.fail_rate` использует глобальный `random`.** Не детерминирован, в тестах не стабилен (хотя `fail_rate=1.0` всегда срабатывает). Если нужны воспроизводимые сценарии — добавим `Random` инстанс в конструктор.
5. **`HttpExternalUserRegistryClient` имеет `client: AsyncClient | None` parameter** — proxy для тестов с `MockTransport`. В проде owns_client=True и сам закрывает в `close()`. Если важен strict DI без этого параметра — переделать на factory-of-client, чтобы тесты передавали свой factory. Текущее проще.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-008: внешний реестр пользователей — `Protocol ExternalUserRegistryClient`, `VerificationResult`, `ExternalApiError`, `MockExternalUserRegistryClient` (YAML + env CSV override), `HttpExternalUserRegistryClient` (httpx + retry 2×backoff для 5xx/сети, 1×Retry-After для 429, sha256-маска телефона в structlog), фабрика `get_registry_client()`. 19 unit-тестов (httpx.MockTransport, без сети). PR [#20](https://github.com/nmetluk/bettgbot/pull/20) → squash `618a431`. Pre-task cleanup [#19](https://github.com/nmetluk/bettgbot/pull/19).
```

## Метрики

- Файлов добавлено: 8 (4 external + 4 tests)
- Строк кода: ~360 (external) + ~330 (tests)
- Тестов добавлено: 19 (всего теперь 78: 41 unit + 4 migrations + 33 repositories)
- Время на выполнение: ~50 мин (включая cleanup PR, фикс фабрики с `get_settings()` вместо module-level `settings`, фикс JSON-body assertion на отсутствие пробела)
