---
id: TASK-031
created: 2026-05-25
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/07-deployment.md
  - infra/docker-compose.prod.yml
  - infra/nginx/admin.conf.template
  - Makefile
priority: normal
estimate: M
---

# TASK-031: Deploy README — пошаговая инструкция выкатки на VPS

## Контекст

Этап 4 близок к финалу: TASK-027 (prod compose) + TASK-028 (handoff backup workflow) + TASK-029 (pg_dump бэкап) + TASK-030 (JSON logging) уже в main. Осталось два задания: **TASK-031 (этот — Deploy README)** и TASK-032 (smoke-тесты после деплоя). После TASK-032 MVP завершён, проект готов к выкатке.

Сейчас в `docs/07-deployment.md` лежит **обзорная** спецификация про compose-стратегию и `.env` — она написана в TASK-003 и обновлялась по ходу Этапа 4 фрагментарно. **Пошаговой инструкции «как взять чистый Ubuntu VPS и поднять прод» нет.** Без неё владелец не сможет:

- развернуть с нуля на новой машине;
- передать workflow другому администратору;
- быстро восстановиться после потери VPS.

Также накопились **известные ограничения**, требующие шагов в bootstrap'e:

- **Certbot не выпустит первый сертификат** автоматически. Цикл такой: nginx нужен сертификат → сертификат выпускается через nginx (challenge `webroot`) → курица-яйцо. Решение — двухфазный bootstrap (http-only nginx → `certbot certonly` → reload с TLS). См. `handoff/outbox/TASK-027-report.md` секция Known limitations.
- **`pg_dump` cron делает первый бэкап через 24 часа** после старта db-backup, если контейнер стартанёт после 02:30 UTC. Mitigation — `make prod.backup.now` сразу после `make prod.up`. См. `sessions/2026-05-25-03-task-029-review/brief.md` минор-секция.
- **JSON-логи в prod**: `LOG_FORMAT=json` уже в `infra/docker-compose.prod.yml` — но это нужно явно упомянуть в README (особенно если оператор будет смотреть `docker logs bot` и ожидать читаемый вывод).

## Цель

Самодостаточный `docs/07-deployment.md` (или новый `docs/09-deploy.md`, если 07 решено оставить как высокоуровневое описание) с пошаговой инструкцией: от чистого `Ubuntu 24.04 LTS` VPS до работающего бота + админки за TLS. После прочтения этого документа человек с базовым опытом Linux должен поднять прод за 30-60 минут, без обращения к cowork-агенту или CC.

## Definition of Done

- [ ] **Новый или обновлённый `docs/07-deployment.md`** (выбрать формат, обсудить в шаге Step 0 — см. ниже) содержит секции:
  1. **Требования к VPS** — минимальные характеристики (1 vCPU, 1-2 GB RAM, 20 GB SSD), Ubuntu 24.04 LTS, открытые порты 80/443.
  2. **DNS** — A-запись `bot.example.com` на IP VPS (объяснить что нужно сделать в панели регистратора домена; не привязываться к конкретному провайдеру).
  3. **Установка зависимостей** — пошаговые `apt install` команды: docker.io, docker-compose-plugin, git, make. Альтернативно — официальный install-скрипт Docker.
  4. **Клонирование репо** — `git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot` + `cd /opt/bettgbot`.
  5. **`.env` setup** — копирование `infra/.env.example` в `infra/.env`, ОБЯЗАТЕЛЬНОЕ заполнение: `TELEGRAM_BOT_TOKEN`, `POSTGRES_PASSWORD`, `ADMIN_SESSION_SECRET`, `ADMIN_CSRF_SECRET`, `ADMIN_DOMAIN`, `TLS_EMAIL`, `LOG_FORMAT=json`. Команды генерации секретов (`python -c 'import secrets; print(secrets.token_urlsafe(48))'`).
  6. **Bootstrap certbot (важно — двухфазный)**:
     - Шаг 6.1: создать временный http-only nginx-конфиг (только `listen 80` + `location /.well-known/acme-challenge/`) — либо описать как делать руками, либо предложить `infra/nginx/admin-bootstrap.conf` который cowork-агент создаст в составе этой задачи как опциональный артефакт.
     - Шаг 6.2: `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d $ADMIN_DOMAIN --email $TLS_EMAIL --agree-tos --no-eff-email`.
     - Шаг 6.3: переключение на full-TLS конфиг (или просто восстановить штатный — после получения certs nginx сразу подхватит).
  7. **Первый запуск:** `make prod.build` → `make prod.up`.
  8. **Первый бэкап** (важно — иначе 24h без бэкапа): `make prod.backup.now`.
  9. **Создание первого админа** для веб-панели: `make admin.create LOGIN=... PASSWORD="..." FULL_NAME="..."`. Объяснить, что это запускается через docker compose в web-контейнере (нужно либо `docker compose exec web make admin.create ...`, либо отдельная prod-цель в Makefile).
  10. **Проверка:** `curl https://$ADMIN_DOMAIN/healthz` → 200 OK; `docker compose -f ... ps` → все сервисы healthy; `make prod.logs` показывает JSON-строки.
  11. **Регулярные операции:**
      - Backup БД — автоматически в 02:30 UTC + `make prod.backup.now` руками.
      - Просмотр логов — `make prod.logs` (или `docker compose ... logs -f bot` для конкретного сервиса).
      - Обновление кода: `git pull && make prod.build && make prod.up`.
  12. **Откат** при проблемах: `git log --oneline` → выбрать предыдущий стабильный коммит → `git checkout <sha> && make prod.build && make prod.up`. Дамп БД — `make prod.backup.restore FILE=...`.

- [ ] **Опционально:** `infra/nginx/admin-bootstrap.conf` — minimal http-only config для шага 6.1 bootstrap'a. Если не делать — описать команду в README пошагово.
- [ ] **Опционально:** новая Makefile-цель `make prod.certbot.init` которая запускает шаг 6.2 одной командой. Уменьшает шанс на опечатку.
- [ ] **Опционально:** Makefile-цель `make admin.create.prod` если штатная `admin.create` плохо запускается в prod (через `docker compose exec web ...`).
- [ ] PR/коммит conventional, один branch.
- [ ] `handoff/outbox/TASK-031-report.md` с **прогоном по бумаге** (имитационный — пройти все шаги README на dev-stack локально, отметить где спотыкаешься, исправить README).
- [ ] **🚨 Move-семантика inbox→archive (`handoff/README.md`):** перед коммитом `chore(handoff): archive TASK-031 ...` — `git rm` обе копии в inbox (`TASK-031-*.md` и `TASK-031.in-progress.md`).
- [ ] **🚨 `make backup`** после merge в main.

## Артефакты

- `* docs/07-deployment.md` (или `+ docs/09-deploy.md` если решено разделить)
- `+ infra/nginx/admin-bootstrap.conf` (опционально)
- `* Makefile` (опционально — `prod.certbot.init`, `admin.create.prod`)
- `+ handoff/outbox/TASK-031-report.md`

## Подсказки исполнителю

### Step 0 — формат документа

Подумай: расширить существующий `docs/07-deployment.md` или создать новый `docs/09-deploy.md` чисто для пошаговой инструкции (а 07 оставить как высокоуровневое описание архитектуры compose-стратегии)?

**Рекомендую первый вариант** — `docs/07-deployment.md` уже про deployment, разделение создаст путаницу «где смотреть». Reorganize content в 07: верх — обзор стратегии (compose файлы, переменные), низ — пошаговый bootstrap.

### Compose v2 правило про -f

Не забудь упомянуть в README: для prod **все** make-цели уже используют `PROD_COMPOSE := docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml`. Прямые вызовы `docker compose ...` без `-f` НЕ подхватят `prod.yml`. Если оператор пытается делать что-то «руками» — пусть либо использует `make prod.*`, либо явно указывает `-f`.

### Документация про .env секреты

Не **публикуй** реальные значения секретов в README — это образец. Используй placeholder'ы (`<your-token>`) и инструкции по генерации. `infra/.env.example` уже служит шаблоном.

### Команды должны быть копируемыми

Каждая команда в README — отдельный код-блок, без префикса `$` (чтобы можно было копировать одной кнопкой и вставить в терминал без чистки). Если команды многострочные — использовать `\` для переноса.

### Что НЕ включать в этот README

- Настройку CI/CD (auto-deploy при push) — отдельная задача за MVP.
- Мониторинг/алертинг (Prometheus, Grafana) — отдельная задача за MVP.
- Multi-server setup (load balancer, шардинг) — заведомо вне MVP.
- Бэкапы offsite (S3, etc.) — заведомо вне MVP (см. TASK-029 «Не делать»).

### Ловушки

1. **`certbot certonly --webroot`** требует **рабочий nginx на порту 80** с `location /.well-known/acme-challenge/` mounting в тот же volume, что и certbot. Без http-only фазы — `connection refused` от Let's Encrypt валидатора.
2. **`make admin.create`** сейчас написан под локальный dev: `PYTHONPATH=. uv run python scripts/create_admin.py`. На VPS uv может не быть установлен. Нужно либо ставить uv в README, либо новая цель `admin.create.prod` через `docker compose exec web python scripts/create_admin.py`.
3. **`POSTGRES_PASSWORD` смены** — если оператор после первого запуска решит сменить пароль, нужно сделать это и в Postgres (`ALTER USER ... WITH PASSWORD ...`), и в `.env`, и `make prod.down && make prod.up`. Записать в раздел «Операционные ситуации».
4. **Доменное имя** — оператор должен убедиться что DNS-запись A `$ADMIN_DOMAIN → IP_VPS` уже распространилась **до** запуска `certbot certonly`. Иначе валидация фейлится.

## Ссылки

- Compose prod: [`infra/docker-compose.prod.yml`](../../infra/docker-compose.prod.yml)
- Nginx template: [`infra/nginx/admin.conf.template`](../../infra/nginx/admin.conf.template)
- Текущий 07-deployment: [`docs/07-deployment.md`](../../docs/07-deployment.md)
- Известные ограничения certbot: [`handoff/outbox/TASK-027-report.md`](../outbox/TASK-027-report.md) секция Known limitations
- pg_dump первый бэкап: [`sessions/2026-05-25-03-task-029-review/brief.md`](../../sessions/2026-05-25-03-task-029-review/brief.md)

**Размер:** M (2-4 часа, в основном — внимательный walkthrough + дописывание `admin.create.prod` / `prod.certbot.init`).
