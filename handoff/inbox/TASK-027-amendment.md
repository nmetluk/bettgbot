# TASK-027-amendment — фиксы перед merge PR #78

**Тип:** amendment к уже выполненной задаче (исходный TASK уже в `handoff/archive/TASK-027-prod-compose/`).
**Базовая ветка:** `feature/TASK-027-prod-compose` (HEAD = `18f8526`).
**Цель:** довести PR #78 до merge-ready состояния. После применения этих фиксов — мержим, обновляем `state/PROJECT_STATUS.md` и стартуем TASK-028.

Cowork-агент провёл review итоговой ветки. Ниже — найденные блокеры и миноры. Все фиксы локализованы в `infra/`, `Makefile`, `handoff/outbox/TASK-027-report.md`. Тесты не затрагиваются.

---

## Блокер 1 — nginx не подставит `${ADMIN_DOMAIN}` в `admin.conf`

**Где:** `infra/nginx/admin.conf` + `infra/docker-compose.prod.yml` (сервис `nginx`).

**Симптом:** nginx сам по себе **не делает envsubst** внутри `.conf`. При текущем монтировании `./nginx/admin.conf:/etc/nginx/conf.d/default.conf:ro` строки `${ADMIN_DOMAIN}` останутся буквальными. `server_name ${ADMIN_DOMAIN};` и пути к certs `/etc/letsencrypt/live/${ADMIN_DOMAIN}/…` сломают и роутинг, и TLS-loadup. Контейнер либо не стартанёт, либо отдаст 404 на всё.

**Фикс (стандартный путь официального образа nginx):**

1. Переименовать `infra/nginx/admin.conf` → `infra/nginx/admin.conf.template`. Содержимое не меняется.
2. В `infra/docker-compose.prod.yml`, сервис `nginx`:
   - Сменить mount на `./nginx/admin.conf.template:/etc/nginx/templates/default.conf.template:ro` (директория `templates/` — триггер для встроенного `envsubst` в docker-entrypoint nginx).
   - Добавить блок:
     ```yaml
     environment:
       ADMIN_DOMAIN: ${ADMIN_DOMAIN}
     ```
   - (Опционально, если хочется явный список разрешённых переменных — добавить `NGINX_ENVSUBST_TEMPLATE_SUFFIX: ".template"`; дефолт уже совпадает, можно не трогать.)

**Acceptance:** `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config | grep server_name` показывает либо подставленный домен (если `.env` подложен), либо корректный шаблон без буквального `${ADMIN_DOMAIN}` в финальном конфиге после старта.

---

## Блокер 2 — `make up` ломает dev-workflow (bot+web стартуют без `--profile full`)

**Где:** `Makefile` (переменная `COMPOSE`) + `infra/docker-compose.override.yml` + `infra/docker-compose.yml`.

**Симптом:** В base `docker-compose.yml` сервисы `bot` и `web` объявлены **без** `profiles:`. `profiles: [full]` живёт только в `override.yml`. Compose v2 правило: **явный `-f path/to/compose.yml` отключает auto-merge override-файла рядом**. Текущий `COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml` тянет ТОЛЬКО base. То есть `make up` теперь поднимет ещё и `bot`+`web` без флага `full`, попытается их сбилдить (`build: ../infra/Dockerfile.{bot,web}`), и упадёт на отсутствующих секретах в `.env` (TG-токен и т.д.). Сломан фундаментальный dev-MO «`make up` = только инфра».

**Фикс — выбор из двух (Recommended: A):**

**A. Явно подключать override в base-COMPOSE (минимальный диффер, сохраняет старый MO):**

```makefile
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.override.yml
```

PROD_COMPOSE уже правильно собран (base + prod). `full.up` остаётся как был — `$(COMPOSE) --profile full up -d`. `make up` опять поднимет только `db+redis`, потому что у `bot`/`web` через override активен `profiles: [full]`.

**B. Перенести `profiles: [full]` на `bot`/`web` в base compose** (тогда override может остаться только с ports + bind-mounts). Чуть чище концептуально, но больше правок и теряется идиома «base = чистая прод-картина без dev-only мелочей».

**Acceptance:** `make up` поднимает только `db` и `redis` (проверить `docker compose ps`), `make full.up` — поднимает четыре сервиса.

---

## Минор 1 — race на `alembic upgrade head` в bot+web

**Где:** `infra/docker-compose.yml`, поля `command:` сервисов `bot` и `web`.

Сейчас оба сервиса при старте делают `alembic upgrade head && ...`. Alembic держит advisory-lock в Postgres, поэтому второй просто подождёт первого — но это лишняя гонка и засорение логов.

**Фикс:** оставить `alembic upgrade head` **только в `web`** (он стартует раньше, отдаёт `/healthz`, миграции — однократный шаг). У `bot` `command` сократить до `python -m src.bot.main`. Опционально добавить `depends_on: web: { condition: service_healthy }` у `bot`, чтобы он гарантированно стартовал после успешного апгрейда.

**Acceptance:** `docker compose up bot web` в чистой БД — миграции применяются один раз, в логах web. У bot в логах нет `Running upgrade …`.

---

## Минор 2 — certbot не выпустит первый сертификат

**Где:** `infra/docker-compose.prod.yml`, сервис `certbot`.

`certbot renew` работает только если certs уже выпущены. На чистом VPS `make prod.up` упадёт: nginx запустится, попытается зачитать `/etc/letsencrypt/live/$ADMIN_DOMAIN/fullchain.pem`, его не будет → exit. Bootstrap-процедура (http-only nginx → `certbot certonly --webroot …` → reload nginx с https) — задача TASK-030 (Deploy README).

**Фикс на этом этапе — документация, не код.** Добавить в `handoff/outbox/TASK-027-report.md` секцию **«Known limitations»** с пунктом:

> Первый запуск на чистом VPS требует ручного `certbot certonly --webroot -w /var/www/certbot -d $ADMIN_DOMAIN --email $TLS_EMAIL --agree-tos` перед `make prod.up`. Bootstrap-процедура будет описана в TASK-030 (Deploy README).

(В TASK-030 я cowork-агент учту это и положу в README пошаговую инструкцию + опциональный `make prod.certbot.init` Makefile-target.)

**Acceptance:** report.md в архиве содержит секцию Known limitations с этой формулировкой (или близкой).

---

## Минор 3 — две косметики

1. **`handoff/outbox/TASK-027-report.md`** — в секции «Diff-сводка» указан несуществующий файл `handoff/inbox/TASK-027.in-progress.md` (516 строк). В реальном diff там `handoff/archive/TASK-027-prod-compose/task.md`. Поправить путь и оставить ту же длину. Тоже самое — обновить в архивной копии (`handoff/archive/TASK-027-prod-compose/task.md` — это сама task, она НЕ меняется; меняется только report).
2. **`infra/docker-compose.yml`** — потерян trailing newline (`\ No newline at end of file`). Добавить пустую строку в конец.

---

## Порядок применения

Всё одной правкой через **fixup-commit** в ту же ветку `feature/TASK-027-prod-compose`. После push'а PR #78 обновится автоматически, CI прогонится снова. После зелёного CI — cowork-агент (я) одобряю, владелец мержит squash.

**Один коммит с conventional message:**

```
fix(infra): TASK-027 amendment — nginx envsubst + Makefile override + alembic race + report fixes

- rename infra/nginx/admin.conf -> admin.conf.template; mount via /etc/nginx/templates/
- add ADMIN_DOMAIN to nginx service environment in prod.yml
- Makefile COMPOSE: append -f infra/docker-compose.override.yml
- docker-compose.yml: drop "alembic upgrade head" from bot command; keep in web
- docker-compose.yml: add trailing newline
- handoff/outbox/TASK-027-report.md: fix Diff-сводка path; add Known limitations section
```

После merge:

1. Cowork-агент (я) обновит `state/PROJECT_STATUS.md` — отметит TASK-027 закрытым, добавит запись о Этапе 4.
2. Cowork-агент проведёт review-сессию `sessions/2026-05-24-XX-task-027-review/`.
3. Положим в inbox **TASK-028** (`pg_dump` cron-бэкап).

---

## Не входит в этот amendment

- Любые правки `src/` или `tests/` — текущей реализации хватает, юнит/integration тесты не задеты.
- Изменения `docs/07-deployment.md` — обновится cowork-агентом в TASK-030.
- Раскопка bootstrap-сценария certbot — там же, в TASK-030.

**Размер:** S (60–90 минут с прогоном CI).

**Blocker:** нет — оба блокера в этом amendment воспроизводимы локально через `docker compose config`/`make up`, фиксы изолированы в `infra/`.
