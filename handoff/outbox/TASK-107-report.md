---
task: TASK-107
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/222
branch: feature/TASK-107-bot-only-on-worker-not-admin
commits:
  - chore(infra): gate bot service behind profile in prod compose (TASK-107)
---
# Отчёт по TASK-107: Бот — только на воркере, не на Admin (repo-фикс топологии)

## Сводка

Реализован постоянный repo-фикс топологии деплоя: сервис `bot` теперь под compose-профилем `bot` в обоих прод-оверлеях. 

- `infra/docker-compose.prod.yml` (для доменного split-деплоя): `bot` под `profiles: ["bot"]` — дефолтный `make prod.up` / PROD_COMPOSE на Admin-сервере больше не поднимает `bot` (только db/redis/db-backup/web/nginx/certbot).
- `infra/docker-compose.prod-no-domain.yml` (single-host bootstrap): аналогично под профилем; для single-host (где бот нужен) make-цели nodomain.* теперь активируют `--profile bot`.
- Обновлён `Makefile`: комментарии, `prod.build` (чтобы собирал и bot-образ), все nodomain.* цели (up/build/down/logs/ps) используют `--profile bot`, `prod.up` оставлен без профиля (теперь явно Admin-only).
- Проверки: `docker compose -f base -f prod.yml config --services` — `bot` отсутствует; с `--profile bot` — присутствует. То же для no-domain. Сервисы инфра/web поднимаются без изменений, без транзитивных depends на bot (в prod-оверлеях bot и так не декларировал depends_on).

Это соответствует диагностике TASK-105/106 (бот на Admin — ошибка, нет egress'а) и готовит почву под worker-only compose (TASK-104).

## Изменённые файлы

```
* infra/docker-compose.prod.yml            # + profiles: ["bot"] под сервисом bot
* infra/docker-compose.prod-no-domain.yml  # + profiles: ["bot"] под сервисом bot (с учётом single-host)
* Makefile                                 # комментарии + --profile bot в nodomain.* и prod.build; правка описания prod.up
 D handoff/inbox/TASK-107-bot-only-on-worker-not-admin.md
?? handoff/inbox/TASK-107-bot-only-on-worker-not-admin.in-progress.md   # transient, будет удалён при archive
```

## Как воспроизвести / запустить

```bash
# 1. Admin-набор (должен НЕ содержать bot)
POSTGRES_USER=... POSTGRES_PASSWORD=... ... ADMIN_DOMAIN=... \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config --services
# Ожидание: bot отсутствует в списке

# 2. С профилем (воркер / single)
... --profile bot config --services | grep bot
# Ожидание: bot в списке

# 3. Make-цели (dry)
make -n prod.up          # без --profile bot (Admin)
make -n prod.nodomain.up # с --profile bot (single-host)

# 4. Реальный старт на машине (после деплоя/передачи .env)
# Admin (split):
make prod.up
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml ps   # bot не должен быть

# Worker (будущий bot-only, или вручную):
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml --profile bot up bot -d
```

## Что не сделано (если применимо)

- Не создавал `infra/docker-compose.bot-only.yml` (упомянут в задаче как TASK-104) — его нет в main, артефакты задачи явно ограничивают только двумя prod.yml + текст в docs. Готово для подключения в будущей задаче (профиль уже есть).
- Не правил `docs/07-deployment.md` — по задаче текст даётся в отчёте, вписывает cowork.
- Не добавлял новые make-цели типа `prod.bot.up` (оставил для TASK-104 / последующих).
- uv.lock и другие не трогал (один spurious diff в lock при прогоне uv был откачен).
- Полный pytest не зелёный (2 фейла в test_prediction_analytics — date-dependent "тайм-бомбы", в скоупе TASK-102, не связаны с нашей правкой инфра; все остальные тесты + lint/type зелёные).

## Открытые вопросы для проектировщика

- Как именно будет выглядеть `docker-compose.bot-only.yml` (TASK-104)? Нужно ли в нём `-f prod.yml --profile bot` или dedicated минимальный файл только с bot + volumes/env? (Я бы предпочёл первый для DRY.)
- Нужно ли обновить `prod.shell.bot` / другие цели, чтобы они всегда передавали `--profile bot` (сейчас exec на работающем контейнере должен работать и без флага)?
- В single-host no-domain (bootstrap) — всегда ли нужен бот при `make prod.nodomain.up`? Если иногда только админка — задокументировать альтернативную команду без профиля.
- После TASK-104/107/108 — стоит ли ввести в Makefile явные `prod.admin.*` цели (явно без профиля) и `prod.worker.*` / `prod.bot.*` (с профилем), чтобы не полагаться на "знай, когда какой флаг"?

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-107: бот только на воркере (не на Admin) — repo-фикс топологии. `bot` под `profiles: ["bot"]` в prod*.yml; Admin-деплой (make prod.up) больше не тянет bot; no-domain single-host активирует профиль в make-целях. Подготовка к bot-only compose. (PR #222)

## Метрики (опционально)

- Тестов добавлено: 0 (инфра, без кода)
- Время на выполнение: ~40 мин (анализ + правки + верификация compose + make dry + отчёт)
