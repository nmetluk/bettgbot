---
id: TASK-008
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/06-external-api.md
  - docs/01-architecture.md
  - docs/08-conventions.md
  - infra/mock-registry.yml
priority: high
estimate: M
---

# TASK-008: Внешний реестр пользователей — интерфейс + mock + HTTP-каркас

## Контекст

После TASK-007 у нас есть persistence + query слои. До сервисов (TASK-009) нужно описать единственную внешнюю интеграцию проекта: реестр пользователей, через который проверяется их телефон при регистрации. `UserService.register_or_authenticate` будет зависеть от интерфейса этого клиента — поэтому реестр идёт первым (см. [`sessions/2026-05-23-06-task-007-review/decisions.md`](../../sessions/2026-05-23-06-task-007-review/decisions.md), решение 6).

Спецификация и предлагаемый контракт — в [`docs/06-external-api.md`](../../docs/06-external-api.md). Образец конфигурации mock — в [`infra/mock-registry.yml`](../../infra/mock-registry.yml).

На этапе разработки используется mock; HTTP-реализация — каркас с настоящим `httpx.AsyncClient`, готовый к подключению к реальному API после согласования контракта.

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: обновлённые `state/PROJECT_STATUS.md` (закрытие TASK-007, новые шаги), `state/DECISIONS.md` (6 новых записей), обновлённый `state/BACKLOG.md` (перестановка TASK-008/009), новая сессия `sessions/2026-05-23-06-task-007-review/`. Упакуй в `chore/post-TASK-007-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-008-external-registry` от свежего `main`.

## Цель

В `src/shared/external/` есть полный комплект: интерфейс `ExternalUserRegistryClient` (`Protocol`), dataclass `VerificationResult`, исключение `ExternalApiError`, две реализации (`MockExternalUserRegistryClient`, `HttpExternalUserRegistryClient`), фабрика `get_registry_client()`, выбирающая реализацию по `settings.external_registry_backend`. Mock конфигурируется YAML-файлом и/или env CSV. HTTP-клиент работает (через `httpx.MockTransport` в тестах), но в prod-конфиге `EXTERNAL_REGISTRY_BACKEND=http` пока не используется. Unit-тесты покрывают оба пути.

## Definition of Done

### `src/shared/external/registry.py` — интерфейс и общие типы

- [ ] `class VerificationResult` — frozen `@dataclass`. Поля:
  - `is_allowed: bool`
  - `external_user_id: str | None`
  - `display_name: str | None`
  - `reason: str | None` — для `not_found` / `blocked`
- [ ] `class ExternalUserRegistryClient(Protocol)`:
  - `async def verify(self, phone: str) -> VerificationResult: ...`
  - Используем `runtime_checkable` чтобы можно было `isinstance(...)` в тестах.
- [ ] `class ExternalApiError(Exception)` — для сетевых сбоев / 5xx / исчерпан ретрай. Принимает опциональный `cause: Exception | None`, сохраняет в `self.__cause__` или поле.
- [ ] Module docstring + `__all__`.

### `src/shared/external/mock_registry.py` — реализация на основе YAML/env

- [ ] `class MockExternalUserRegistryClient` реализует `ExternalUserRegistryClient`.
- [ ] Конструктор принимает: `allowed: dict[str, AllowedEntry]`, `blocked: dict[str, str]`, `latency_ms: int`, `fail_rate: float`. Не дёргает settings напрямую — это делает фабрика.
- [ ] Метод `verify(phone)`:
  - Если `simulate.fail_rate > 0` и случайный roll внутри — `raise ExternalApiError("simulated failure")`.
  - Если `latency_ms > 0` — `await asyncio.sleep(latency_ms / 1000)`.
  - Если `phone in blocked` — `VerificationResult(is_allowed=False, ..., reason=blocked[phone])`.
  - Если `phone in allowed` — `VerificationResult(is_allowed=True, external_user_id=..., display_name=...)`.
  - Иначе — `VerificationResult(is_allowed=False, ..., reason="not_found")`.
- [ ] Helper-классы / TypedDict для `AllowedEntry` (поля `external_user_id`, `display_name | None`) и `BlockedEntry` — на твоё усмотрение; главное — типизированно.

### `src/shared/external/http_registry.py` — реализация на httpx

- [ ] `class HttpExternalUserRegistryClient` реализует `ExternalUserRegistryClient`.
- [ ] Конструктор принимает: `base_url: str`, `token: str`, `timeout_connect: float`, `timeout_read: float`, и опционально `client: httpx.AsyncClient | None` (для тестов с `MockTransport`). Если `client is None` — создаёт собственный с настройками таймаутов.
- [ ] Метод `verify(phone)`:
  - `POST {base_url}/users/verify` с телом `{"phone": phone}` и заголовками `Authorization: Bearer {token}`, `X-Request-Id: {uuid4().hex}`.
  - Парсит ответы по таблице из [`docs/06-external-api.md`](../../docs/06-external-api.md):
    - `200 {"status":"ok",...}` → `VerificationResult(is_allowed=True, ...)`
    - `200 {"status":"not_found"}` → `VerificationResult(is_allowed=False, reason="not_found")`
    - `200 {"status":"blocked","reason":...}` → `VerificationResult(is_allowed=False, reason=...)`
    - `401` → `ExternalApiError("unauthorized")` (не ретраим)
    - `429` с `Retry-After` → один ретрай уважая заголовок
    - `5xx` или сетевая ошибка → exponential backoff (0.5s, 1s), максимум 2 ретрая → `ExternalApiError(...)`
    - `4xx` кроме 401/429 → `ExternalApiError(...)` (не ретраим)
- [ ] **Логирование** через `get_logger(__name__)` каждого вызова с полями:
  - `external_api.endpoint = "users.verify"`
  - `external_api.phone_hash = sha256(phone)[:8]` (PII не светим)
  - `external_api.status_code`
  - `external_api.latency_ms`
  - `external_api.retry_count`
  - `external_api.outcome` ∈ `{ok, not_found, blocked, error}`
- [ ] `async def close(self) -> None` — закрывает внутренний клиент; `async def __aenter__` / `__aexit__` для удобства.
- [ ] Никакого использования `httpx.Client` (sync) — только `httpx.AsyncClient`.

### `src/shared/external/__init__.py` — фабрика

- [ ] Re-export: `ExternalUserRegistryClient`, `VerificationResult`, `ExternalApiError`, `MockExternalUserRegistryClient`, `HttpExternalUserRegistryClient`, `get_registry_client`.
- [ ] `def get_registry_client() -> ExternalUserRegistryClient`:
  - Читает `settings.external_registry`.
  - `backend == "http"` → создаёт `HttpExternalUserRegistryClient(base_url=..., token=..., timeout_connect=..., timeout_read=...)`. Валидация Settings уже гарантирует, что `api_base_url` и `api_token` заданы (см. `_check_http_backend_has_credentials` в `Settings`).
  - `backend == "mock"` → загружает конфиг из `settings.external_registry.mock_registry_file` (YAML) и/или `settings.external_registry.mock_registry_allowed` (env CSV — приоритетнее файла, как описано в [`docs/06-external-api.md`](../../docs/06-external-api.md)). Создаёт `MockExternalUserRegistryClient`.
- [ ] Helper `_load_mock_config(file: Path | None, allowed_csv: list[str]) -> tuple[dict, dict, int, float]` — внутри `mock_registry.py` или в фабрике. Парсит YAML структуру из [`infra/mock-registry.yml`](../../infra/mock-registry.yml):
  ```yaml
  allowed:
    - phone: "+71111111111"
      external_user_id: "u-001"
      display_name: "..."
  blocked:
    - phone: "+79999999999"
      reason: "..."
  simulate:
    latency_ms: 50
    fail_rate: 0.0
  ```
  Если `allowed_csv` непустой — он перекрывает `allowed` из файла (телефоны добавляются с `external_user_id=None`, `display_name=None`).

### Тесты

`tests/unit/external/`:

- [ ] `tests/unit/external/__init__.py` (пустой)
- [ ] `tests/unit/external/test_mock_registry.py`:
  - `test_allowed_returns_is_allowed_true`
  - `test_not_found_returns_is_allowed_false_with_reason_not_found`
  - `test_blocked_returns_is_allowed_false_with_reason`
  - `test_csv_allowed_overrides_yaml` — пишем yaml + env CSV, проверяем, что CSV выигрывает
  - `test_yaml_loaded_from_file` — tmp_path с YAML
  - `test_simulate_fail_rate_1_always_raises_external_api_error`
  - `test_simulate_latency_ms_awaits` — `freezegun` + `pytest-asyncio` или просто `time.monotonic()` до/после
- [ ] `tests/unit/external/test_http_registry.py` — все на `httpx.MockTransport`, никаких реальных запросов:
  - `test_200_ok_returns_allowed`
  - `test_200_not_found`
  - `test_200_blocked_with_reason`
  - `test_401_unauthorized_raises_no_retry` — handler инкрементирует counter, проверяем `counter == 1`
  - `test_5xx_then_200_succeeds_after_retry`
  - `test_5xx_three_times_raises_external_api_error`
  - `test_429_with_retry_after_respected` — две попытки, между ними ждём `Retry-After` (мокаем sleep или просто проверяем число вызовов)
  - `test_request_includes_phone_in_body_and_auth_header`
  - `test_request_generates_x_request_id`
  - `test_timeout_raises_external_api_error_after_retries` — handler raises `httpx.ReadTimeout`
- [ ] `tests/unit/external/test_factory.py`:
  - `test_get_registry_client_mock_backend_returns_mock`
  - `test_get_registry_client_http_backend_returns_http` (monkeypatch env `EXTERNAL_REGISTRY_BACKEND=http` + base_url + token + `get_settings.cache_clear()`)

### Качество и workflow

- [ ] `uv run mypy src/shared` — зелёный (strict). Особое внимание: `Protocol` с async-методами требует `runtime_checkable` для `isinstance`; `dict[str, AllowedEntry]` пусть будет `TypedDict` или `dataclass` — главное типизированно.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — 22 старых unit + 16+ новых.
- [ ] `uv run pytest tests/integration -m integration` — 37 как и были.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] Ветка `feature/TASK-008-external-registry`, Conventional Commits:
  - `feat(external): registry interface + types`
  - `feat(external): mock registry client`
  - `feat(external): http registry client with retry`
  - `feat(external): factory get_registry_client`
  - `test(external): mock + http + factory tests`
  - Или один-два сжатых коммита — на твоё усмотрение.
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-008-report.md`, задача → `handoff/archive/TASK-008-external-registry/task.md`.

## Артефакты

```
+ src/shared/external/__init__.py
+ src/shared/external/registry.py
+ src/shared/external/mock_registry.py
+ src/shared/external/http_registry.py
+ tests/unit/external/__init__.py
+ tests/unit/external/test_mock_registry.py
+ tests/unit/external/test_http_registry.py
+ tests/unit/external/test_factory.py
```

## Ссылки

- [docs/06-external-api.md](../../docs/06-external-api.md) — контракт API, retry-политика, формат лога, mock-конфиг
- [docs/01-architecture.md](../../docs/01-architecture.md) — sequence «Регистрация пользователя», где UserService вызывает registry
- [docs/08-conventions.md](../../docs/08-conventions.md) — стиль логов `logger.info("event", k=v)`, никаких сервисных методов в моделях
- [infra/mock-registry.yml](../../infra/mock-registry.yml) — пример YAML-конфига mock'а
- [src/shared/config.py](../../src/shared/config.py) — `ExternalRegistrySettings`, валидатор «http backend → token и url обязательны»

## Подсказки исполнителю

- **`httpx.MockTransport`** — это удобный способ юнит-тестить без реальной сети. Пример:
  ```python
  import httpx

  def make_handler(responses: list[httpx.Response]):
      iter_resp = iter(responses)
      def handler(request: httpx.Request) -> httpx.Response:
          return next(iter_resp)
      return handler

  transport = httpx.MockTransport(make_handler([httpx.Response(500), httpx.Response(200, json={...})]))
  async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
      reg = HttpExternalUserRegistryClient(base_url="http://test", token="t", ..., client=client)
      result = await reg.verify("+71111111111")
  ```
- **Sleep между ретраями.** В проде — `await asyncio.sleep(...)`. В тестах подменяй через `monkeypatch.setattr("src.shared.external.http_registry.asyncio.sleep", AsyncMock())` или передавай `sleep` callable через конструктор.
- **`Retry-After` парсинг.** Может быть в секундах (`"30"`) или HTTP-date (`"Wed, 21 Oct 2026 07:28:00 GMT"`). Парсь оба формата, второй — через `email.utils.parsedate_to_datetime`. На MVP достаточно секунд.
- **`X-Request-Id`** — генерируется на каждый запрос свежим `uuid.uuid4().hex`. Не путать с retry'ями: при ретрае тот же запрос имеет тот же ID (это полезно для tracing).
- **Хеш телефона** — `import hashlib; hashlib.sha256(phone.encode()).hexdigest()[:8]`. PII не светим в логах.
- **Импорт `yaml`** — `pyyaml` уже в `pyproject.toml` (TASK-002), `types-pyyaml` тоже.
- **`Protocol` + `@runtime_checkable`** — нужен, чтобы `isinstance(client, ExternalUserRegistryClient)` работал в тестах. mypy без него не возражает, но `isinstance` упадёт.
- **`asyncio.timeout` / `httpx.Timeout`** — для запроса используй `httpx.Timeout(connect=timeout_connect, read=timeout_read, write=timeout_read, pool=timeout_read)`. `connect` отдельно — потому что подключение зависает в другой фазе.
- **Возврат `await close()`** — при использовании DI (TASK-009 и далее) и при тестах будет важно. Делай это `aiohttp`-style: `__aenter__`/`__aexit__` + `async def close()`.
- **Унификация: оба клиента имеют одинаковую сигнатуру конструктора** — НЕ обязательно. У них разные требования. Главное — общий метод `verify`.
- **`get_registry_client()` не кэшируется** — на каждый вызов делаем нового клиента. Если позже окажется, что нужен singleton (например, чтобы переиспользовать HTTP connection pool), добавим `@lru_cache`. На MVP кэшировать преждевременно.

## Что НЕ делать

- Не писать `UserService` и его интеграцию с registry — это TASK-009.
- Не запускать реальные сетевые запросы из тестов (используй `httpx.MockTransport`).
- Не подключать `tenacity` или другие retry-библиотеки — у нас 2 ретрая, реализация в 10 строк.
- Не подключать `python-dotenv`, sentry, OTel, prometheus.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md`.
- Не модифицировать `infra/mock-registry.yml` — он образец и эталон формата.
- Не вводить factory-boy / responses / pytest-httpx — `httpx.MockTransport` достаточен и не добавляет deps.
