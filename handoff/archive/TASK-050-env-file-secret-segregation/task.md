---
id: TASK-050
created: 2026-05-27
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - infra/docker-compose.yml
  - infra/docker-compose.prod.yml
  - infra/docker-compose.prod-no-domain.yml
  - docs/audit/2026-05-25-mvp-audit.md  # H-18 (не оформлено задачей)
priority: high
estimate: S
---

# TASK-050: Разделить `.env` по сервисам — db-backup и nginx не должны видеть `TELEGRAM_BOT_TOKEN`/`ADMIN_*`

## Контекст

Auditor MVP отметил находку **H-18** (`docs/audit/2026-05-25-mvp-audit.md`): «`env_file: ../.env` в bot/web/db-backup → утечка из любого контейнера = утечка из всех». В P1 roadmap'е она есть, но **в `handoff/inbox/` под неё не было задачи**. Доукомплектовываю.

Фактическая проблема, проверенная по коду:

```yaml
# infra/docker-compose.prod.yml
db-backup:
    env_file: ../.env       # ← получает TELEGRAM_BOT_TOKEN, ADMIN_SECRET_KEY,
                            #    ADMIN_CSRF_SECRET, EXTERNAL_API_TOKEN — все секреты
    environment:
      PGPASSWORD: ${POSTGRES_PASSWORD}
```

Тот же шаблон в `infra/docker-compose.prod-no-domain.yml`. Сервис `db-backup` фактически нуждается только в `POSTGRES_USER/PASSWORD/DB` и `PGPASSWORD`. Получает всё.

Последствия:
- RCE в bot или web → читает `/proc/1/environ` и берёт `POSTGRES_PASSWORD` (это, кстати, ровно сценарий, который H-18 описывал).
- RCE в db-backup (теоретически — он минимальный postgres-alpine, но `pg_dump` — bug-attack surface) → даёт `TELEGRAM_BOT_TOKEN` и `ADMIN_SECRET_KEY`. **Это session forging для админки.**
- Логи docker inspect / `docker compose config` пишут все env переменные в plain — оператор без подготовки видит секреты.

Дополнительная проблема — `bot` контейнеру **не нужен** `ADMIN_SECRET_KEY` и `ADMIN_CSRF_SECRET` (он не валидирует cookie админки), `web` контейнеру не нужен `TELEGRAM_BOT_TOKEN`. Кросс-secret-exposure.

## Цель

Каждый контейнер получает только те секреты, которые ему реально нужны. `env_file: ../.env` заменяется на явные `environment:` blocks либо разделённые `.env.<service>` файлы.

## Definition of Done

- [ ] Создать `infra/.env.bot.example`, `infra/.env.web.example`, `infra/.env.db.example` — каждый с минимальным набором.
- [ ] В `infra/docker-compose.yml` базовая сервис-структура использует `environment:` блоки **со списком конкретных переменных** через `${VAR}` интерполяцию (не `env_file:` целиком). Пример:
  ```yaml
  bot:
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      EXTERNAL_REGISTRY_BACKEND: ${EXTERNAL_REGISTRY_BACKEND:-mock}
      EXTERNAL_API_BASE_URL: ${EXTERNAL_API_BASE_URL:-}
      EXTERNAL_API_TOKEN: ${EXTERNAL_API_TOKEN:-}
      MOCK_REGISTRY_FILE: ${MOCK_REGISTRY_FILE:-}
      ENVIRONMENT: ${ENVIRONMENT:-dev}
  web:
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      ADMIN_SECRET_KEY: ${ADMIN_SECRET_KEY}
      ADMIN_CSRF_SECRET: ${ADMIN_CSRF_SECRET}
      ADMIN_SESSION_HOURS: ${ADMIN_SESSION_HOURS:-8}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ENVIRONMENT: ${ENVIRONMENT:-dev}
  db-backup:
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_DB: ${POSTGRES_DB}
      PGPASSWORD: ${POSTGRES_PASSWORD}
  ```
- [ ] Убрать `env_file: ../.env` из всех services в base + prod + prod-no-domain.
- [ ] `infra/.env.example` остаётся как «полный список переменных, для удобства» — но не подключается напрямую через `env_file:`.
- [ ] `docs/07-deployment.md` обновить: «секреты подключаются явно per-service через `environment:` блоки в compose, не одним общим `env_file:`».
- [ ] Smoke-проверка `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config` без warnings, `make prod.up` поднимает все сервисы, `docker inspect db-backup` НЕ показывает `TELEGRAM_BOT_TOKEN`.
- [ ] PR `TASK-050: per-service env segregation`.
- [ ] Отчёт + Move-семантика inbox→archive.

## Артефакты

- `* infra/docker-compose.yml` (base) — `environment:` блоки вместо `env_file:`
- `* infra/docker-compose.prod.yml` — то же для prod
- `* infra/docker-compose.prod-no-domain.yml` — то же
- `* infra/docker-compose.override.yml` — то же (dev)
- `+ infra/.env.bot.example`, `infra/.env.web.example`, `infra/.env.db.example` — для документации
- `* docs/07-deployment.md` — обновить раздел про .env

## Подсказки исполнителю

- `environment: { KEY: ${KEY:-default} }` — стандартный compose-паттерн. Если `KEY` пуст в `.env` — подставляется default. Если default нет и переменная не задана — compose warning'ует (это полезно, не глуши).
- `infra/.env.bot.example` и т. п. — для документации, какие переменные **этому** сервису реально нужны. Реальный `.env` всё ещё один файл на VPS (общий для compose-интерполяции).
- Альтернатива (если хочется ещё строже) — Docker Secrets / SOPS, но это P2 (M-19 в аудите).
- **Не разворачивай это без TASK-034 (валидация секретов)** — если оператор соберёт неполный `.env`, compose warning'ует, но prod-валидатор должен **отказаться стартовать**.
