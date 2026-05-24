# TASK-027: Production docker-compose + Dockerfile.{bot,web} + nginx — отчёт

## Что сделано

- `.dockerignore` в корне репо — исключает dev-артефакты (tests, docs, handoff, etc.) из Docker образов
- `infra/Dockerfile.bot` — multi-stage build, non-root user, uv sync, healthcheck
- `infra/Dockerfile.web` — аналогично + EXPOSE 8000 + healthcheck через urllib
- `infra/docker-compose.yml` — расширен базовый compose: добавлены bot и web сервисы
- `infra/docker-compose.override.yml` — dev-расширения: ports, bind-mounts, profile=full
- `infra/docker-compose.prod.yml` — prod-расширения: nginx, certbot, log rotation, restart: always
- `infra/nginx/admin.conf` — TLS + HSTS + gzip + proxy_pass web:8000
- `Makefile` — добавлены prod.* targets (build, up, down, logs, ps, shell.bot, shell.web)
- `infra/.env.example` — добавлены ADMIN_DOMAIN и TLS_EMAIL
- `.gitignore` — обновлён для versioned override файла

## Коммиты

- `3c0c9de` feat(infra): Dockerfile.bot и Dockerfile.web (multi-stage, non-root, uv sync)

## Что НЕ сделано

- docs/07-deployment.md не обновлён — заготовка осталась из TASK-026, но разметка уже соответствует трёхфайловой схеме
- .dockerignore не содержит infra/docker-compose.override.yml — исправлено после проверки .gitignore

## Тесты

- Unit tests: 227 passed
- Linting: ruff check/format clean
- Typecheck: mypy clean (shared/bot/admin)
- Smoke-проверка не проводилась (требует .env с секретами)

## Команды для воспроизведения

```bash
# локально с .env
make prod.build   # собрать образы
make prod.up      # поднять prod-stack (без .env упадёт)

# dev-stack
make full.up      # поднять db+redis+bot+web в контейнерах (profile=full)
```

## Diff-сводка

```
.dockerignore                                 |  19 ++
.gitignore                                    |   3 +-
Makefile                                      |  29 +-
handoff/archive/TASK-027-prod-compose/task.md | 516 ++++++++++++++++++++++++++++
infra/.env.example                            |   3 +
infra/Dockerfile.bot                          |  35 +++
infra/Dockerfile.web                          |  37 +++
infra/docker-compose.override.yml             |  26 ++
infra/docker-compose.prod.yml                 |  55 ++++
infra/docker-compose.yml                      |  36 ++-
infra/nginx/admin.conf                        |  47 ++++
```

## PR

https://github.com/nmetluk/bettgbot/pull/78 (squash-merge → `7a35016`)

## Known limitations (зафиксировано в hotfix PR cowork-агентом 2026-05-25)

Первый запуск на чистом VPS **не сработает «из коробки»**: `certbot renew` (как настроен в `infra/docker-compose.prod.yml`) обновляет уже существующие сертификаты, но не выпускает первый. Bootstrap-процедура:

1. Поднять nginx в http-only режиме (временный конфиг без `listen 443 ssl`).
2. `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d $ADMIN_DOMAIN --email $TLS_EMAIL --agree-tos --no-eff-email`.
3. Переключить nginx на full-TLS конфиг, перезапустить.

Полная пошаговая инструкция и опциональный `make prod.certbot.init` target — задача **TASK-031 (Deploy README)** по обновлённой нумерации Этапа 4.

## Hotfix-правки от cowork-агента (2026-05-25, после merge PR #78)

Cowork-агент по итогам code review зафиксировал две блокерные проблемы и применил hotfix в отдельной ветке `fix/TASK-027-nginx-envsubst-and-makefile-override`:

1. **nginx envsubst.** `infra/nginx/admin.conf` → `infra/nginx/admin.conf.template`; в `prod.yml` mount изменён на `/etc/nginx/templates/default.conf.template` + добавлен `environment: ADMIN_DOMAIN`. Без этого `${ADMIN_DOMAIN}` в конфиге оставался буквальной строкой и nginx не находил серты.
2. **Makefile COMPOSE.** К базовой `COMPOSE`-переменной добавлен `-f infra/docker-compose.override.yml`. Без этого `make up` поднимал bot+web вне `profiles: [full]` (compose v2 не auto-merge'ит override при явном `-f base.yml`), что ломало dev-MO «`make up` = только инфра».
3. **`alembic upgrade head` race.** Убрано из `bot.command`, оставлено только в `web.command`. У `bot` добавлен `depends_on: web: { condition: service_healthy }` — миграции применяются один раз через web, bot ждёт.
4. **Trailing newline** в `infra/docker-compose.yml`.
5. **Эта секция** — фикс косметики Diff-сводки + Known limitations.