---
id: TASK-032
created: 2026-05-25
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/07-deployment.md
  - infra/docker-compose.prod.yml
  - Makefile
priority: normal
estimate: S
---

# TASK-032: Smoke-тесты после деплоя

## Контекст

Финальная задача Этапа 4. После TASK-027..031 у нас есть prod docker-compose + бэкапы + JSON logging + Deploy README. Не хватает только **автоматизированной проверки**, что после `make prod.up` всё реально живо: web отдаёт `/healthz` 200, bot подключился к Telegram, миграции применены до актуальной версии. Без этого деплой считается «прошёл» только по факту отсутствия ошибок в `docker compose up -d`, что недостаточно.

После TASK-032 MVP завершён, проект готов к выкатке на VPS.

## Цель

Скрипт `scripts/smoke_test.sh`, который запускается **после** `make prod.up` (либо вручную после деплоя, либо в CD-pipeline когда таковой появится), и проверяет:

1. **Web `/healthz`** возвращает HTTP 200 в течение 60 секунд после старта.
2. **Bot контейнер живой** (`docker compose ps` показывает healthy / running).
3. **Alembic** — текущая ревизия БД совпадает с head в коде (`alembic current` == `alembic heads`).
4. **db-backup** контейнер живой и хотя бы поллит (можно проверить через `docker compose ps`).

Запускается через `make prod.smoke` (новая Makefile-цель).

## Definition of Done

- [ ] **`scripts/smoke_test.sh`** (исполняемый, cross-platform не требуется — запускается на VPS, Linux). Структура:
  ```sh
  #!/usr/bin/env bash
  set -euo pipefail
  
  echo "→ Checking web /healthz..."
  for i in $(seq 1 12); do
      if curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/healthz | grep -q 200; then
          echo "  ✓ web /healthz OK"
          break
      fi
      [ "$i" -eq 12 ] && { echo "  ✗ web /healthz не отвечает за 60s"; exit 1; }
      sleep 5
  done
  
  echo "→ Checking docker compose services..."
  # ... через PROD_COMPOSE ps --format json + jq, или текстовый match по "healthy"/"running"
  
  echo "→ Checking alembic version..."
  # docker compose exec -T web alembic current vs alembic heads
  
  echo "✓ Smoke tests passed"
  ```
- [ ] **`Makefile`** цель `prod.smoke` (через `.PHONY` + вызов скрипта).
- [ ] **`docs/07-deployment.md`** — в секции «Проверка» (шаг 10 в README по TASK-031) добавить: «или одной командой: `make prod.smoke`».
- [ ] **Idempotent**: повторный запуск даёт тот же результат (не мутирует состояние).
- [ ] **Exit code** 0 при успехе, 1 при первой неудаче (set -e + явные exit).
- [ ] **Понятный вывод**: каждая проверка — отдельная строка с `→` и `✓`/`✗`. Финальная строка `✓ Smoke tests passed` или явное сообщение об ошибке.
- [ ] **🚨 Move-семантика inbox→archive** (`handoff/README.md` + CI-check включен): перед коммитом `chore(handoff): archive TASK-032 ...` — `git rm` обе копии в inbox. CI handoff-consistency теперь будет блочить merge при нарушении.
- [ ] **🚨 `make backup`** после merge в main.
- [ ] PR/коммит conventional.
- [ ] `handoff/outbox/TASK-032-report.md` с **реальным прогоном на dev-stack**: `make full.up` + `make prod.smoke` (с переопределением COMPOSE на dev — либо `prod.smoke` должна работать против любого compose-конфига).

## Артефакты

- `+ scripts/smoke_test.sh`
- `* Makefile` — цель `prod.smoke` + добавление в `.PHONY`
- `* docs/07-deployment.md` — упомянуть `make prod.smoke` в секции «Проверка»
- `+ handoff/outbox/TASK-032-report.md`

## Подсказки исполнителю

### Endpoint бота

У бота **нет HTTP healthz** в текущей реализации (он long-polling, не webhook). Поэтому проверка через docker compose ps + healthy статус (из Dockerfile `HEALTHCHECK`). Альтернатива — экспозиция `/healthz` в bot, но это лишний работ для MVP. **Используй docker compose ps.**

### Alembic check

Простой способ:

```sh
current=$(docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml exec -T web alembic current 2>/dev/null | grep -oE '^[a-f0-9]+')
head=$(docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml exec -T web alembic heads 2>/dev/null | grep -oE '^[a-f0-9]+')
[ "$current" = "$head" ] || { echo "✗ Alembic out of sync: current=$current, head=$head"; exit 1; }
```

### Compose контекст

Скрипт **должен** уметь работать с любым compose-конфигом (dev для CI, prod для VPS). Самый простой способ — переменная `BB_COMPOSE_ARGS`:

```sh
COMPOSE="docker compose ${BB_COMPOSE_ARGS:--f infra/docker-compose.yml -f infra/docker-compose.prod.yml}"
```

Тогда на VPS: `make prod.smoke` (использует дефолт = prod). На CI / dev: `BB_COMPOSE_ARGS='-f infra/docker-compose.yml -f infra/docker-compose.override.yml' ./scripts/smoke_test.sh`.

### Retry-loop для /healthz

Web стартует в 5-30 секундах (миграции + uvicorn). Loop с 5s sleep × 12 раз = до 60s wait — щадящий timeout.

### Не делай

- Не пиши e2e-тест с реальным Telegram-запросом — за MVP. /healthz и docker ps достаточно.
- Не запускай pytest из smoke — медленно и требует тестовой БД. Smoke != полноценный test suite.
- Не добавляй cleanup (down -v) после smoke — это **проверка живого**, не setup-teardown.

## Ссылки

- Healthcheck web: [`infra/Dockerfile.web`](../../infra/Dockerfile.web) — есть `HEALTHCHECK CMD python -c 'import urllib...'`
- Healthcheck bot: [`infra/Dockerfile.bot`](../../infra/Dockerfile.bot) — есть `HEALTHCHECK CMD python -c 'from src.shared.config import get_settings...'`
- Compose prod: [`infra/docker-compose.prod.yml`](../../infra/docker-compose.prod.yml)
- Deploy README: [`docs/07-deployment.md`](../../docs/07-deployment.md) секция «Проверка»

**Размер:** S (1-1.5 часа). После закрытия — **MVP завершён**.
