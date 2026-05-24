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
.dockerignore                         |  19 ++
.gitignore                            |   3 +-
Makefile                              |  29 +-
handoff/inbox/TASK-027.in-progress.md | 516 ++++++++++++++++++++++++++++++++++
infra/.env.example                    |   3 +
infra/Dockerfile.bot                  |  35 +++
infra/Dockerfile.web                  |  37 +++
infra/docker-compose.override.yml     |  26 ++
infra/docker-compose.prod.yml         |  55 ++++
infra/docker-compose.yml              |  36 ++-
infra/nginx/admin.conf                |  47 ++++
```

## PR

https://github.com/nmetluk/bettgbot/pull/78