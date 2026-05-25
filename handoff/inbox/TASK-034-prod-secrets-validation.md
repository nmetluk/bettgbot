---
id: TASK-034
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: S
---

# TASK-034: Валидация секретов и backend'а в `Settings` для prod-окружения

## Контекст

Аудит MVP 2026-05-25, находка **C-02 (Critical, CWE-798/521)**. Сейчас `.env` содержит дефолтные dev-значения (`ADMIN_SECRET_KEY=dev-admin-secret`, `ADMIN_CSRF_SECRET=dev-csrf-secret`, `POSTGRES_PASSWORD=changeme`, `TELEGRAM_BOT_TOKEN=dev-bot-token`). При случайном copy-paste dev-`.env` на prod-VPS `Settings` примет эти значения без замечаний. Forging signed-cookie сессии тривиально → захват админки.

Дополнительно: `EXTERNAL_REGISTRY_BACKEND=mock` в prod пускает регистрацию через `infra/mock-registry.yml` — обходит реальную верификацию.

## Цель

`Settings()` при `environment != "dev"` **fails fast** с понятным сообщением, если:
1. `admin.secret_key` или `admin.csrf_secret` содержат подстроки `dev-`, `changeme`, `secret`, или короче 32 символов.
2. `telegram_bot_token` равен `dev-bot-token` или короче 30 символов (TG-токены ≥ 35).
3. `external_registry.backend == "mock"`.
4. `log_format == "console"` (для prod должен быть `json`).

## Definition of Done

- [ ] `src/shared/config.py` имеет `@model_validator(mode="after")` в `Settings`, который при `self.environment != "dev"` поднимает `ValueError` с конкретным указанием невалидного поля.
- [ ] Список «слабых» подстрок-маркеров секрета вынесен в module-level константу `_WEAK_SECRET_MARKERS = frozenset({"dev-", "changeme", "secret", "test"})`.
- [ ] Валидатор покрыт unit-тестами в `tests/unit/test_config.py`:
  - `environment=dev` + dev-секрет → ОК.
  - `environment=prod` + dev-секрет → ValueError с понятным `loc`.
  - `environment=prod` + сильный секрет (`token_urlsafe(64)`) → ОК.
  - `environment=prod` + `EXTERNAL_REGISTRY_BACKEND=mock` → ValueError.
  - `environment=prod` + `LOG_FORMAT=console` → ValueError.
- [ ] `.env.example` (`infra/.env.example`) обновлён: в комментариях явно сказано «для prod сгенерировать через `python -c "import secrets; print(secrets.token_urlsafe(64))"`».
- [ ] Создан `infra/.env.prod.example` с пометками «обязательные для prod» (включает `ADMIN_DOMAIN`, `TLS_EMAIL`, `ENVIRONMENT=prod`, плейсхолдеры для секретов).
- [ ] `docs/07-deployment.md` обновлён: пошагово «как сгенерировать prod-секреты».
- [ ] PR в GitHub, имя `TASK-034: validate prod secrets in Settings`.
- [ ] Отчёт в `handoff/outbox/TASK-034-report.md`.
- [ ] **🚨 Move-семантика inbox→archive** (см. handoff/README.md).
- [ ] **🚨 `make backup` после merge в main**.

## Артефакты

- `* src/shared/config.py` — `_WEAK_SECRET_MARKERS`, новый `@model_validator`
- `* tests/unit/test_config.py` — 5 новых тестов
- `* infra/.env.example` — комментарии по генерации секретов
- `+ infra/.env.prod.example` — новый
- `* docs/07-deployment.md` — раздел про секреты

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-02
- Конвенция: `docs/08-conventions.md` (Settings — extra=ignore — не противоречит валидатору)

## Подсказки

- Валидатор должен **не** падать когда `model_validator` запускается с `ENVIRONMENT=dev` через `monkeypatch.setenv` в тестах — иначе все остальные тесты сломаются.
- Тесты на валидатор требуют `get_settings.cache_clear()` перед каждым кейсом (паттерн уже принят в проекте).
- В сообщении ошибки указать **какое именно** поле невалидно (`admin.secret_key`, не общее «секрет слаб»).
