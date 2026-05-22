# 06 — Внешний API проверки пользователей (контракт + mock)

Документ определяет:

1. Что мы ожидаем от внешней системы (предлагаемый контракт — отправляется владельцу системы на согласование).
2. Как этот контракт скрыт за интерфейсом в коде.
3. Какой mock мы используем на этапе разработки.

## Зачем

Регистрация в боте разрешена только для пользователей, чьи телефоны уже есть во внешнем реестре. Сами мы пользователей в реестр не заводим — только проверяем.

## Предлагаемый контракт (черновик для согласования)

**Endpoint:** `POST {EXTERNAL_API_BASE_URL}/users/verify`

**Авторизация:** заголовок `Authorization: Bearer {EXTERNAL_API_TOKEN}`.

**Request:**

```http
POST /users/verify HTTP/1.1
Content-Type: application/json
Authorization: Bearer ...
X-Request-Id: 9f1c... (uuid, для трассировки)

{
  "phone": "+71234567890"
}
```

`phone` — строго E.164.

**Responses:**

| HTTP | Тело | Семантика |
|---|---|---|
| `200 OK` | `{"status":"ok","external_user_id":"abc-123","display_name":"Иван Иванов"}` | Найден, разрешён. `display_name` опционально. |
| `200 OK` | `{"status":"not_found"}` | Не найден — отказать в регистрации. |
| `200 OK` | `{"status":"blocked","reason":"..."}` | Найден, но заблокирован — отказать. |
| `400` | `{"error":"invalid_phone"}` | Неверный формат — ошибка нашей валидации, не должна приходить. |
| `401` | `{"error":"unauthorized"}` | Невалидный токен — алерт. |
| `429` | `{"error":"rate_limited","retry_after":N}` | Слишком много запросов; уважать `Retry-After`. |
| `5xx` | произвольное | Внешняя ошибка; ретрай по политике ниже. |

**Идемпотентность:** запрос идемпотентен (только чтение); повторы безопасны.

**SLA (запрашиваем у владельца):** p95 ≤ 500ms, доступность ≥ 99.5%.

## Политика ретраев и таймаутов

- Connection timeout: 2s, read timeout: 5s.
- Ретраи: до 2 повторов на 5xx и сетевые ошибки, exponential backoff (0.5s, 1s).
- На 429 — один ретрай с уважением `Retry-After`.
- 4xx (кроме 429) не ретраим.
- На исчерпание ретраев — поднимаем `ExternalApiError` с подробным контекстом; бот отвечает пользователю «Не удалось проверить номер прямо сейчас, попробуйте позже».

## Интерфейс в коде

Файл: `src/shared/external/registry.py`.

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True)
class VerificationResult:
    is_allowed: bool
    external_user_id: str | None
    display_name: str | None
    reason: str | None    # для not_found / blocked

class ExternalUserRegistryClient(Protocol):
    async def verify(self, phone: str) -> VerificationResult: ...

class ExternalApiError(Exception):
    """Сеть/5xx/исчерпан ретрай. Бот покажет пользователю generic-ошибку."""
```

Бизнес-сервис (`UserService`) принимает зависимость по интерфейсу — никогда не импортирует конкретную реализацию напрямую.

## Реализации

### `HttpExternalUserRegistryClient`

Файл: `src/shared/external/http_registry.py`. На основе `httpx.AsyncClient`. Конфиг — из `Settings`:

```
EXTERNAL_API_BASE_URL=https://registry.example.com
EXTERNAL_API_TOKEN=...
EXTERNAL_API_TIMEOUT_CONNECT=2.0
EXTERNAL_API_TIMEOUT_READ=5.0
```

### `MockExternalUserRegistryClient` (для разработки и тестов)

Файл: `src/shared/external/mock_registry.py`.

Поведение задаётся конфигом (приоритет сверху вниз):

1. **Список разрешённых телефонов** в env: `MOCK_REGISTRY_ALLOWED=+71111111111,+72222222222`. Если задан — только эти телефоны проходят.
2. **YAML-файл** в env `MOCK_REGISTRY_FILE=./infra/mock-registry.yml` со структурой:
   ```yaml
   allowed:
     - phone: "+71111111111"
       external_user_id: "u-001"
       display_name: "Тест Один"
     - phone: "+72222222222"
       external_user_id: "u-002"
   blocked:
     - phone: "+79999999999"
       reason: "test-block"
   simulate:
     latency_ms: 100        # искусственная задержка для реалистичности
     fail_rate: 0.0         # доля запросов, отвечающих ExternalApiError
   ```
3. **Default**: пустые списки, всё → `not_found`.

В тестах подменяется напрямую через DI без файлов.

### Выбор реализации

В `src/shared/external/__init__.py`:

```python
from src.shared.config import settings

if settings.external_registry_backend == "http":
    from .http_registry import HttpExternalUserRegistryClient as Client
elif settings.external_registry_backend == "mock":
    from .mock_registry import MockExternalUserRegistryClient as Client
else:
    raise ValueError(...)
```

`settings.external_registry_backend` — переменная `EXTERNAL_REGISTRY_BACKEND ∈ {http, mock}`. В dev и CI — `mock`, в prod — `http` (после согласования контракта).

## Логирование и наблюдаемость

Каждый вызов внешнего API логируется (`structlog`) с полями:

- `external_api.endpoint = users.verify`
- `external_api.phone_hash = sha256(phone)[:8]` (не сам телефон — это PII)
- `external_api.status_code`
- `external_api.latency_ms`
- `external_api.retry_count`
- `external_api.outcome ∈ {ok, not_found, blocked, error}`

Метрики (на будущее, не на MVP): счётчик вызовов по outcome, гистограмма latency.

## Что отдать владельцу внешней системы для согласования

Готовый PDF/MD с разделом «Предлагаемый контракт» выше + примеры curl-запросов и ответов. Получив ответ — обновить этот документ и переключить `EXTERNAL_REGISTRY_BACKEND=http`.

## Открытые вопросы для согласования

- Точный путь endpoint (`/users/verify` vs `/api/v1/users/verify`).
- Заголовок авторизации и схема (Bearer vs другая).
- Формат `external_user_id` (uuid / int / строка).
- Что считать «заблокирован» — отдельный статус или просто `not_found`?
- SLA и rate limits.

## Связанное

- [01-architecture.md](01-architecture.md), [04-bot-flows.md](04-bot-flows.md)
