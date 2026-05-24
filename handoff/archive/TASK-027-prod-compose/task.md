---
id: TASK-027
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/07-deployment.md
  - docs/02-tech-stack.md
  - docs/adr/0004-no-build-backend.md
  - infra/docker-compose.yml
priority: high
estimate: L
---

# TASK-027: Production docker-compose + Dockerfile.{bot,web} + nginx — старт Этапа 4

## Контекст

**Первая задача Этапа 4 — production deployment.** До сих пор `infra/docker-compose.yml` содержал только инфраструктуру (db + redis), `bot` и `web` запускались с хоста (`uv run python -m src.bot.main` / `make admin`). Нужно собрать **end-to-end** прод-ready setup: bot + web в контейнерах, nginx как TLS-прокси, healthchecks, log rotation.

Спецификация в [`docs/07-deployment.md`](../../docs/07-deployment.md) описывает целевую топологию:

```
VPS (Ubuntu LTS):
  nginx (host или контейнер) → /admin/* → web:8000 (uvicorn)
  docker compose:
    bot   (long-polling в Telegram API, no public port)
    web   (uvicorn :8000, доступен через nginx)
    db    (postgres:16, volume)
    redis (redis:7, volume)
```

**Ключевые архитектурные решения** (зафиксированы):
- [ADR-0004](../../docs/adr/0004-no-build-backend.md): без `pip install -e .` / wheel-сборки. Dockerfile делает `COPY src /app/src` + `ENV PYTHONPATH=/app`.
- Compose v2 трёхфайловая схема: base + override (dev) + prod (`-f` явно). Зафиксировано в `2026-05-23-02-task-003-review`.
- Telegram-бот через long-polling (не webhook) — спека `docs/07` раздел «Топология».
- Alembic upgrade в `command` обоих сервисов через `sh -c "alembic upgrade head && ..."` — `Alembic` берёт advisory lock в Postgres, гонок нет.

Источники:

- [`docs/07-deployment.md`](../../docs/07-deployment.md) — целиком, особенно секции «Раскладка compose-файлов», «Dockerfile-ы», «Переменные окружения».
- [`infra/docker-compose.yml`](../../infra/docker-compose.yml) — текущий dev-only.
- [`docs/adr/0004-no-build-backend.md`](../../docs/adr/0004-no-build-backend.md) — нет build-backend.
- [`pyproject.toml`](../../pyproject.toml) — `uv` dependency manager, lock-file `uv.lock`.

## Перед стартом — pre-task cleanup PR

В origin/main `538f18b` — last commit (archive TASK-026). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-026 + Этапа 3, новый шаг TASK-027.
- Новая сессия `sessions/2026-05-24-13-task-026-review/`.
- `handoff/inbox/TASK-027-prod-compose.md` — эта задача.

Branch: `chore/post-TASK-026-cowork-cleanup`, PR, merge. После — `feature/TASK-027-prod-compose`.

## Цель

Команды `make prod.build && make prod.up` поднимают **полный prod-stack**: bot + web + db + redis + nginx с TLS. `make admin` (dev) продолжает работать как раньше (uvicorn с reload, доступ через `http://127.0.0.1:8000`). Тест-инфраструктура (CI) не ломается. Документация в `docs/07` обновляется под фактическую реализацию.

## Definition of Done

### Step 1 — Dockerfile.bot и Dockerfile.web

#### `infra/Dockerfile.bot`

- [ ] **Multi-stage build** с `python:3.12-slim`:
  ```dockerfile
  # --- builder ---
  FROM python:3.12-slim AS builder

  RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      && rm -rf /var/lib/apt/lists/*

  # uv через pip — потом sync без dev-зависимостей
  RUN pip install --no-cache-dir uv==0.5.0

  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev --no-install-project

  # --- runtime ---
  FROM python:3.12-slim AS runtime

  RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
      && rm -rf /var/lib/apt/lists/* \
      && groupadd -r bb && useradd -r -g bb -d /app -s /sbin/nologin bb

  WORKDIR /app
  COPY --from=builder /app/.venv /app/.venv
  COPY --chown=bb:bb src /app/src
  COPY --chown=bb:bb alembic.ini /app/

  ENV PATH="/app/.venv/bin:$PATH" \
      PYTHONPATH="/app" \
      PYTHONUNBUFFERED=1 \
      PYTHONDONTWRITEBYTECODE=1

  USER bb

  # Healthcheck: проверка, что python работоспособен и Settings импортируется
  HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
      CMD python -c "from src.shared.config import get_settings; get_settings()" || exit 1

  CMD ["python", "-m", "src.bot.main"]
  ```
  - **`uv` через pip** в builder — простой способ получить uv в Docker (альтернатива — `astral/uv` image, но добавляет специфику).
  - **`--no-install-project`** — потому что `pyproject.toml` имеет `[tool.uv] package = false` (ADR-0004); реальные исходники копируются в runtime stage.
  - **`libpq5` в runtime** — нужен для `psycopg2` / `asyncpg` (asyncpg обычно не требует, но защита от регрессий).
  - **`USER bb` non-root** — security best practice.
  - **`HEALTHCHECK` проверяет Settings()** — простая проверка работоспособности. Если БД недоступна, бот сам падает, и compose рестартует.

#### `infra/Dockerfile.web`

- [ ] **Аналогичный Dockerfile, отличия:**
  - `EXPOSE 8000` (информативная — uvicorn слушает 0.0.0.0:8000).
  - `CMD ["uvicorn", "src.admin.app:app", "--host", "0.0.0.0", "--port", "8000"]`.
  - `HEALTHCHECK CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1` (нужен `curl` в runtime — `apt-get install curl` либо `python -c "..."` через urllib).
  - **Альтернатива healthcheck без curl** (чтобы не тащить пакет):
    ```dockerfile
    HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5).read()" || exit 1
    ```
  - Я предпочитаю **python-вариант** — без дополнительных пакетов.

#### `.dockerignore` (новый файл в корне репо)

- [ ] **`.dockerignore`** (новый файл, **в корне репо**, не в `infra/`):
  ```
  .git
  .gitignore
  .github
  .venv
  __pycache__
  *.pyc
  .ruff_cache
  .mypy_cache
  .pytest_cache
  tests
  docs
  handoff
  sessions
  state
  scripts
  *.md
  uv.lock.backup
  .env
  .env.*
  infra/docker-compose.override.yml
  ```
  - **Не копировать в образ** dev-зависимости, тесты, документацию — уменьшает size образа.
  - **`.env` исключён** — secrets подсасываются через `env_file:` в compose.

### Step 2 — Расширить `infra/docker-compose.yml` (base)

- [ ] Добавить сервисы `bot` и `web` в текущий dev-only файл:
  ```yaml
  name: bettgbot

  services:
    db:
      # (без изменений, как сейчас)
      ...

    redis:
      # (без изменений)
      ...

    bot:
      build:
        context: ..
        dockerfile: infra/Dockerfile.bot
      restart: unless-stopped
      env_file: ../.env
      depends_on:
        db: { condition: service_healthy }
        redis: { condition: service_healthy }
      command: >
        sh -c "alembic upgrade head && python -m src.bot.main"
      # Без портов наружу — long-polling в Telegram

    web:
      build:
        context: ..
        dockerfile: infra/Dockerfile.web
      restart: unless-stopped
      env_file: ../.env
      depends_on:
        db: { condition: service_healthy }
      command: >
        sh -c "alembic upgrade head && uvicorn src.admin.app:app --host 0.0.0.0 --port 8000"
      # Порт наружу — через nginx (prod) или через override (dev)

  volumes:
    pg_data:
    redis_data:
  ```
  - **`context: ..`** — потому что Dockerfile в `infra/`, а исходники в `src/` (корень репо).
  - **`alembic upgrade head` в `command` обоих сервисов** — оба пытаются, Alembic берёт advisory lock, гонок нет (см. `docs/07`).
  - **`depends_on` с `condition: service_healthy`** — ждём, пока БД пройдёт healthcheck.

### Step 3 — `infra/docker-compose.override.yml` (dev)

- [ ] **Новый файл** — dev-расширения:
  ```yaml
  # Dev-overrides. Compose v2 автоматически подхватывает этот файл рядом с base.
  services:
    db:
      ports:
        - "127.0.0.1:5432:5432"

    redis:
      ports:
        - "127.0.0.1:6379:6379"

    bot:
      restart: "no"  # в dev не рестартуем — пусть упадёт явно
      volumes:
        - ../src:/app/src:ro  # hot-reload через bind-mount (Python autoreload не работает для aiogram polling)
      # Для dev можно отказаться от bot вообще, запускать `make bot` с хоста
      profiles:
        - full  # bot стартует только с `docker compose --profile full up`

    web:
      restart: "no"
      ports:
        - "127.0.0.1:8000:8000"
      volumes:
        - ../src:/app/src:ro
      command: >
        sh -c "alembic upgrade head && uvicorn src.admin.app:app --host 0.0.0.0 --port 8000 --reload"
      profiles:
        - full
  ```
  - **`profiles: full`** — bot и web стартуют только при `docker compose --profile full up`. Без флага — только db+redis (как сейчас). Это даёт чистый dev-flow: тяжёлые контейнеры опциональны.
  - **`--reload` в web** — uvicorn пересобирает при изменении файлов.
  - **`volumes: ro`** — read-only bind-mount; запись в `/app/src` из контейнера не нужна.

### Step 4 — `infra/docker-compose.prod.yml` (prod)

- [ ] **Новый файл** — prod-расширения:
  ```yaml
  # Prod-overrides. Запуск: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
  services:
    db:
      # restart: always — выше base.unless-stopped, в prod строже
      restart: always
      # Никаких exposed ports

    redis:
      restart: always
      # Никаких exposed ports

    bot:
      restart: always
      # Логирование через JSON-driver с rotation (TASK-029 точнее настроит format)
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "3"

    web:
      restart: always
      logging:
        driver: json-file
        options:
          max-size: "10m"
          max-file: "3"

    nginx:
      image: nginx:1.27-alpine
      restart: always
      ports:
        - "80:80"
        - "443:443"
      volumes:
        - ./nginx/admin.conf:/etc/nginx/conf.d/default.conf:ro
        - certbot_certs:/etc/letsencrypt:ro
        - certbot_www:/var/www/certbot:ro
      depends_on:
        web: { condition: service_healthy }
      healthcheck:
        test: ["CMD", "wget", "-q", "-O", "-", "http://127.0.0.1/healthz"]
        interval: 30s
        timeout: 5s
        retries: 3

    # Опционально: certbot для автоматического renewal Let's Encrypt.
    # На первый запуск — manual cert через `docker run --rm certbot/certbot ...`,
    # потом этот сервис обновляет.
    certbot:
      image: certbot/certbot:latest
      restart: unless-stopped
      volumes:
        - certbot_certs:/etc/letsencrypt
        - certbot_www:/var/www/certbot
      entrypoint: >
        sh -c "trap exit TERM;
               while :; do certbot renew --webroot -w /var/www/certbot --quiet;
                           sleep 12h & wait $${!}; done"

  volumes:
    certbot_certs:
    certbot_www:
  ```
  - **`logging` JSON-file rotation** — 10MB × 3 файла = max 30MB логов на сервис. TASK-029 настроит format (JSON).
  - **`nginx` как контейнер** (не на хосте) — упрощает деплой. `volumes` bind-mount config + cert volumes.
  - **`certbot` контейнер** — auto-renewal каждые 12 часов. Первичная инициализация — manual (см. TASK-030 deploy README).
  - **`web` без exposed ports** — доступен только через `nginx`.

### Step 5 — `infra/nginx/admin.conf`

- [ ] **Новый файл** — nginx config для админки:
  ```nginx
  # HTTP → HTTPS redirect
  server {
      listen 80;
      server_name ${ADMIN_DOMAIN};

      # ACME challenge для certbot
      location /.well-known/acme-challenge/ {
          root /var/www/certbot;
      }

      # Healthcheck — без redirect'а
      location = /healthz {
          return 200 'ok';
          add_header Content-Type text/plain;
      }

      # Всё остальное → HTTPS
      location / {
          return 301 https://$host$request_uri;
      }
  }

  # HTTPS proxy → web:8000
  server {
      listen 443 ssl http2;
      server_name ${ADMIN_DOMAIN};

      ssl_certificate /etc/letsencrypt/live/${ADMIN_DOMAIN}/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/${ADMIN_DOMAIN}/privkey.pem;
      ssl_protocols TLSv1.2 TLSv1.3;
      ssl_ciphers HIGH:!aNULL:!MD5;
      ssl_session_cache shared:SSL:10m;

      # Security headers
      add_header Strict-Transport-Security "max-age=63072000" always;
      add_header X-Frame-Options DENY always;
      add_header X-Content-Type-Options nosniff always;

      gzip on;
      gzip_types text/plain text/css application/javascript application/json image/svg+xml;
      gzip_min_length 1024;

      # Limit body для безопасности (форма с JSON metadata может быть до 1MB)
      client_max_body_size 1m;

      location / {
          proxy_pass http://web:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_read_timeout 30s;
      }
  }
  ```
  - **`${ADMIN_DOMAIN}`** — переменная окружения. Чтобы nginx её резолвил, нужен либо envsubst при `entrypoint`, либо хардкодить домен в conf. Проще: **первый деплой делает manual `envsubst < admin.conf.template > admin.conf`** перед `docker compose up`. Документируется в TASK-030. **На MVP можно захардкодить** `server_name betgbot.example.com` и менять руками при первом деплое.
  - **`/healthz` в HTTP-блоке** без redirect — для cloud-провайдеров (LB-healthcheck), которым нужен HTTP, не HTTPS.
  - **TLSv1.2+** — minimum. Старые TLSv1.0/1.1 deprecated.
  - **`client_max_body_size 1m`** — для безопасности.

### Step 6 — Makefile targets

- [ ] **Добавить в `Makefile`:**
  ```makefile
  .PHONY: prod.build prod.up prod.down prod.logs prod.ps prod.shell.bot prod.shell.web

  PROD_COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml

  prod.build: ## Собрать prod-образы bot+web
  	$(PROD_COMPOSE) build

  prod.up: ## Поднять prod-stack (с nginx)
  	$(PROD_COMPOSE) up -d
  	$(PROD_COMPOSE) ps

  prod.down: ## Остановить prod-stack
  	$(PROD_COMPOSE) down

  prod.logs: ## Tail prod-логов всех сервисов
  	$(PROD_COMPOSE) logs -f --tail=100

  prod.ps: ## Статус prod-сервисов
  	$(PROD_COMPOSE) ps

  prod.shell.bot: ## Открыть shell в prod bot-контейнере
  	$(PROD_COMPOSE) exec bot sh

  prod.shell.web: ## Открыть shell в prod web-контейнере
  	$(PROD_COMPOSE) exec web sh
  ```
- [ ] **Обновить `make full.up` для dev** (опц. — full-stack локально):
  ```makefile
  full.up: ## Поднять полный dev-stack (db + redis + bot + web в контейнерах)
  	docker compose --env-file .env -f infra/docker-compose.yml --profile full up -d
  ```

### Step 7 — `.env.example` обновить

- [ ] **В `infra/.env.example`** добавить:
  ```
  # --- DEPLOYMENT ---
  ENVIRONMENT=dev  # prod / staging / dev

  # --- ADMIN DOMAIN (для prod nginx) ---
  ADMIN_DOMAIN=betgbot.example.com
  TLS_EMAIL=admin@example.com  # для certbot

  # ... existing vars
  ```

### Step 8 — Документация: обновить `docs/07-deployment.md`

- [ ] Заменить «заготовка TASK-026» секции на фактическую реализацию (`Dockerfile.{bot,web}`, override+prod compose, nginx config).
- [ ] Добавить секцию «Первичный TLS-cert через certbot» с manual командой:
  ```bash
  docker run --rm \
      -v bettgbot_certbot_certs:/etc/letsencrypt \
      -v bettgbot_certbot_www:/var/www/certbot \
      -p 80:80 \
      certbot/certbot certonly --standalone \
      -d $ADMIN_DOMAIN -m $TLS_EMAIL --agree-tos -n
  ```
  Затем уже `make prod.up`.
- [ ] Обновить таблицу «Раскладка compose-файлов» под фактическое.

### Step 9 — Smoke-проверка локальная

- [ ] **На своей машине** (не в DoD CI):
  - `make prod.build` — собирается без ошибок.
  - `make prod.up` — поднимается; `prod.ps` показывает все сервисы healthy через ~30 секунд.
  - `curl http://127.0.0.1/healthz` (через nginx) → 200.
  - `make prod.shell.web; alembic current` — миграция применена.
  - `make prod.down` — корректно останавливается.
- [ ] **CI** этого не покрывает (требует docker-in-docker, лишняя ceremony для GH Actions). Smoke-тесты после деплоя — TASK-031.

### Step 10 — Регрессия: тесты не сломались

- [ ] `uv run pytest -m "not integration"` — все 227 unit.
- [ ] `uv run pytest tests/integration -m integration` — все 116 integration.
- [ ] CI на PR — 4 зелёных (тесты + lint + typecheck + integration alembic).

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный (если что-то меняли в src/).
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] Ветка `feature/TASK-027-prod-compose`, Conventional Commits:
  - `feat(infra): Dockerfile.bot и Dockerfile.web (multi-stage, non-root, uv sync)`
  - `feat(infra): расширить compose базу bot+web + override.yml (dev profile) + prod.yml (nginx+certbot+log rotation)`
  - `feat(infra): nginx admin.conf — TLS + HSTS + gzip + proxy_pass web:8000`
  - `feat(infra): .dockerignore в корне`
  - `chore(makefile): prod.build/up/down/logs/ps/shell targets`
  - `docs(deployment): обновить под фактическую реализацию TASK-027`
  - `feat(env): ADMIN_DOMAIN + TLS_EMAIL в .env.example`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-027-report.md`, задача → `handoff/archive/TASK-027-prod-compose/task.md`.

## Артефакты

```
+ infra/Dockerfile.bot                              # multi-stage non-root
+ infra/Dockerfile.web                              # multi-stage non-root + healthcheck via urllib
+ .dockerignore                                     # в корне репо
* infra/docker-compose.yml                          # +bot, web сервисы (база без портов)
+ infra/docker-compose.override.yml                 # dev: ports, bind-mounts, profile=full
+ infra/docker-compose.prod.yml                     # prod: nginx, certbot, log rotation, restart: always
+ infra/nginx/admin.conf                            # TLS + HSTS + proxy_pass
* infra/.env.example                                # +ADMIN_DOMAIN, +TLS_EMAIL, +ENVIRONMENT
* Makefile                                          # +prod.* targets
* docs/07-deployment.md                             # обновить под фактическую реализацию
```

## Ссылки

- [docs/07-deployment.md](../../docs/07-deployment.md) — целевая топология
- [docs/adr/0004-no-build-backend.md](../../docs/adr/0004-no-build-backend.md) — без wheel-сборки
- [docs/02-tech-stack.md](../../docs/02-tech-stack.md) — uvicorn, postgres:16, redis:7
- [infra/docker-compose.yml](../../infra/docker-compose.yml) — текущий dev-only

## Подсказки исполнителю

- **`uv sync --frozen --no-dev --no-install-project`** — `--no-install-project` критично из-за ADR-0004 (нет build-backend, проект сам по себе не устанавливается). `--frozen` гарантирует точное соответствие `uv.lock`.
- **`COPY src /app/src`** + `ENV PYTHONPATH=/app` — стандарт ADR-0004. Никаких `pip install -e .`.
- **`USER bb` non-root** — нужен `groupadd -r bb && useradd -r -g bb`. `WORKDIR /app` + `COPY --chown=bb:bb`.
- **`alembic upgrade head` в `command`** — оба сервиса (bot и web) запускают миграции. Гонок не будет благодаря advisory lock в Postgres. Альтернатива (только bot мигрирует) — асимметрия, web блокируется ожиданием bot'а в depends_on. Проще оба.
- **`profiles: full`** в override.yml — bot/web стартуют только с `--profile full`. Без — только db+redis. Это сохраняет текущий dev-flow `make up`.
- **Healthcheck для web через python+urllib** (не curl) — не нужен extra apt package. Простой и работает.
- **`server_name ${ADMIN_DOMAIN}` в nginx.conf** — nginx сам по себе **не интерполирует** env vars. Решение: либо envsubst при `entrypoint`, либо хардкод. **На первом деплое — хардкод** через `sed -i s/example.com/realdomain/ admin.conf`. Documented в TASK-030.
- **`certbot` standalone** для первого cert — temporarily останавливаем nginx (`prod.down nginx`), запускаем `certbot certonly --standalone`, обратно `prod.up`. После — auto-renew через `certbot` контейнер.
- **`logging` JSON-file driver** — стандарт Docker, rotation встроен. Альтернатива (`fluentd`, `journald`) — overengineering для MVP.
- **Размер runtime-образа**: с `python:3.12-slim` + venv = ~200-300MB. Multi-stage без dev-deps. Если хочется меньше — `python:3.12-alpine`, но `psycopg2` / `asyncpg` потребуют extra build deps (musl vs glibc). Slim — компромисс.

## Что НЕ делать

- **Не делать pip install -e .** или wheel-сборку — ADR-0004 запрещает.
- **Не делать webhook** для Telegram — long-polling по решению (docs/07).
- **Не делать kubernetes / swarm** — docker-compose достаточно для одного VPS.
- **Не настраивать CI deploy** — TASK-031 покрывает smoke-тесты после deploy; авто-deploy через GitHub Actions — отдельная задача после MVP.
- **Не создавать systemd unit** — docker-compose с `restart: always` + автозапуск Docker через apt-install достаточны. Спека `docs/07`.
- **Не вынимать secrets в Docker secrets** — `.env` через `env_file:` достаточно для одного VPS. Vault / secrets manager — переоптимизация.
- Не лезть в `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
