---
id: TASK-041
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: S
---

# TASK-041: Sentry для ошибок + Healthchecks.io ping для bot/scheduler

## Контекст

Аудит MVP 2026-05-25, находка **C-09**. Логи через structlog JSON — только в локальных Docker-файлах (60 MB ring-buffer, ~6h истории под нагрузкой). Никакого Sentry для ошибок. Никакого external uptime monitoring. Первый prod-инцидент будет обнаружен пользователями.

## Цель

1. **Sentry** — все unhandled exceptions из бота и админки летят в Sentry с tagging `service=bot|admin`, `environment=prod|staging|dev`.
2. **Healthchecks.io ping** — `dispatch_reminders` scheduler-job каждые 5 минут пингует Healthchecks UUID. Если 15 минут тишины — Healthchecks алертит владельца (email/telegram).
3. Конфиг через env, отключается в dev (DSN/UUID = пусто → no-op).

## Definition of Done

- [ ] `Settings` имеет:
  - `sentry_dsn: SecretStr | None = None`
  - `sentry_traces_sample_rate: float = 0.1` (10% для perf-monitoring)
  - `healthchecks_ping_url: HttpUrl | None = None`
- [ ] Валидатор: `environment != "dev"` ⇒ `sentry_dsn is not None` (warning, не error — Sentry опционален, но рекомендуется).
- [ ] `pyproject.toml` deps: `sentry-sdk[fastapi]>=2.0,<3`.
- [ ] `src/shared/observability.py` (новый) — `init_sentry()` фабрика, вызывается из `src/bot/main.py:main()` и `src/admin/app.py:lifespan`.
  - Bot integration: добавить `LoggingIntegration` (structlog) + ручной `sentry_sdk.set_tag("service", "bot")`.
  - Admin integration: `FastApiIntegration` + `StarletteIntegration` + `sentry_sdk.set_tag("service", "admin")`.
- [ ] `src/bot/scheduler/jobs.py:dispatch_reminders` после успешного завершения тика делает `httpx.get(settings.healthchecks_ping_url, timeout=5)` (fire-and-forget, ошибка не валит job).
- [ ] Дополнительно: `dispatch_reminders` использует `healthchecks_ping_url + "/fail"` при необработанной ошибке (для алерта).
- [ ] Unit-тесты: `init_sentry()` с None DSN — no-op (не падает); с DSN — `sentry_sdk.Hub.current.client` is not None.
- [ ] Integration-тест: пингующая обёртка вокруг `dispatch_reminders` не валит job если healthchecks URL недоступен.
- [ ] `docs/07-deployment.md` обновлён:
  - Раздел «Создать Sentry проект, получить DSN».
  - Раздел «Создать Healthchecks.io ping endpoint, прописать в `.env`».
- [ ] `infra/.env.example` + `.env.prod.example` — `SENTRY_DSN=`, `HEALTHCHECKS_PING_URL=`.
- [ ] PR в GitHub, имя `TASK-041: Sentry + Healthchecks.io integration`.
- [ ] Отчёт в `handoff/outbox/TASK-041-report.md`.
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `* src/shared/config.py` — Sentry/Healthchecks settings
- `+ src/shared/observability.py` — `init_sentry()`
- `* src/bot/main.py` — `init_sentry()` в startup
- `* src/admin/app.py` — `init_sentry()` в lifespan
- `* src/bot/scheduler/jobs.py` — healthchecks ping
- `+ tests/unit/test_observability.py`

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-09
- Sentry FastAPI: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Healthchecks.io: https://healthchecks.io/

## Подсказки

- Sentry free tier: 5k events/month — хватит на MVP, при росте проверить usage.
- `sentry-sdk[fastapi]` уже включает Starlette integration.
- `LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)` — INFO как breadcrumbs, ERROR как event.
- Не отправляй в Sentry PII — Sentry-SDK имеет `before_send` hook: вырезать `user.phone`, `user.first_name` (но `user.id` — ок).
- Healthchecks-ping URL — это HTTPS GET, никаких заголовков не нужно. Timeout 5s достаточно. Падение — лог warning, job не falling.
