---
id: TASK-029
created: 2026-05-25
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/07-deployment.md
  - infra/docker-compose.prod.yml
  - state/PROJECT_STATUS.md
priority: normal
estimate: M
---

# TASK-029: pg_dump cron-бэкап БД в Docker volume

## Контекст

После закрытия TASK-027 (prod docker-compose + hotfix) и TASK-028 (handoff backup workflow) в Этапе 4 production deployment осталось четыре задачи: TASK-029 (этот pg_dump бэкап), TASK-030 (structured JSON logging), TASK-031 (Deploy README на VPS), TASK-032 (smoke-тесты после деплоя). После TASK-032 MVP завершён.

База — PostgreSQL 16 в контейнере `db` сервиса compose. Сейчас данные хранятся в named volume `pg_data`. **Бэкапа нет вообще** — потеря volume = полная потеря данных пользователей, прогнозов, событий. Это блокер для prod-deploy: владелец не может выкатить бот, пока не уверен, что переживёт потерю диска / случайный `docker volume rm`.

## Цель

Регулярный (раз в сутки) `pg_dump` БД в отдельный именованный Docker volume `bb-db-backups` с retention 14 дней. Запускается через cron-контейнер на том же compose-стеке, без внешних зависимостей. После TASK-029 владелец может уверенно стартовать prod-deploy в TASK-031.

## Definition of Done

- [ ] Новый сервис `db-backup` в `infra/docker-compose.prod.yml` на образе `postgres:16-alpine` с cron-демоном (busybox crond + crontab или sh-loop через `sleep 86400`). Запускается раз в сутки (рекомендую 02:30 UTC — после `archive_stale_events` job'a бота в 03:00). Подключён к сети compose, имеет `depends_on: db: { condition: service_healthy }`.
- [ ] Сервис `db-backup` пишет дампы в named volume `bb-db-backups`, смонтированный как `/backups`. Volume объявлен в `infra/docker-compose.prod.yml` секция `volumes:`.
- [ ] Формат имени дампа: `bettgbot-YYYY-MM-DDTHH-MM-SSZ.sql.gz` (UTC timestamp, gzip — экономит ~5-10x на текстовом дампе). Команда генерации: `pg_dump --no-owner --clean --if-exists | gzip > /backups/bettgbot-$(date -u +%FT%H-%M-%SZ).sql.gz`.
- [ ] **Retention 14 дней.** После каждого нового дампа: `find /backups -name 'bettgbot-*.sql.gz' -mtime +14 -delete`. Делать **после** успешного pg_dump (если pg_dump упал — старые не удалять, иначе можем потерять единственный рабочий бэкап).
- [ ] Сервис устойчив к `pg_dump` failure: при ошибке логировать stderr с явным префиксом `[backup-error]`, НЕ удалять старые, НЕ падать (продолжать loop). Это для алертинга через `docker logs` (полноценный alerting — отдельная задача за MVP).
- [ ] **Тест восстановления** (документация в report'е, не в коде): команда `docker compose exec db-backup ls -lah /backups` показывает дампы. Команда `docker compose exec db sh -c 'gunzip -c /backups/<file>.sql.gz | psql -U $POSTGRES_USER $POSTGRES_DB'` восстанавливает (на стенде, не на проде).
- [ ] Makefile цели:
  - `make prod.backup.now` — однократный pg_dump прямо сейчас (без ожидания cron).
  - `make prod.backup.ls` — список бэкапов в volume.
  - `make prod.backup.restore FILE=...` — восстановление из указанного файла (с подтверждением через `read ans; [ "$ans" = "RESTORE" ]` как у `make nuke`).
- [ ] `infra/.env.example` — если появятся новые переменные (например `BACKUP_RETENTION_DAYS=14`), задокументировать.
- [ ] PR/коммит conventional, один branch.
- [ ] `handoff/outbox/TASK-029-report.md` — секция о ручном smoke-тесте (`make prod.backup.now` запустить локально на dev compose, убедиться что файл появился в volume через `docker volume inspect bb-db-backups`).

## Артефакты

- `* infra/docker-compose.prod.yml` — новый сервис `db-backup` + volume `bb-db-backups`
- `+ infra/db-backup/Dockerfile` — если возьмём custom image поверх `postgres:16-alpine` (например для добавления `dcron` или своего entrypoint). Альтернатива: использовать `postgres:16-alpine` напрямую с `command:` containing inline-loop. **Рекомендую второй вариант** для простоты — без отдельного Dockerfile, всё в compose.
- `+ infra/db-backup/backup.sh` — backup-скрипт (если выносить inline-команды). Mount-ить в контейнер через volume `./db-backup/backup.sh:/usr/local/bin/backup.sh:ro`.
- `* Makefile` — 3 новые цели (`prod.backup.now`, `prod.backup.ls`, `prod.backup.restore`)
- `* infra/.env.example` — если добавим env
- `+ handoff/outbox/TASK-029-report.md`

## Подсказки исполнителю

### Cron vs sleep-loop

В alpine `postgres:16-alpine` есть `busybox crond` (через `dcron` пакет, надо `apk add dcron`). Альтернатива — sh-loop:

```sh
while true; do
    sleep_until_2_30_UTC
    /usr/local/bin/backup.sh
done
```

Sleep-loop проще и не требует дополнительных пакетов. Cron — стандартнее, но требует `apk add dcron` + `/etc/crontabs/root`. **Рекомендую sleep-loop** для MVP — меньше moving parts, легче дебажить через `docker logs`.

### Подключение к БД

Сервис `db-backup` должен знать как подключиться к `db`. Варианты:
- (а) `env_file: ../.env` — наследует `POSTGRES_USER/PASSWORD/DB`. Используется в `pg_dump -h db -U $POSTGRES_USER $POSTGRES_DB`.
- (б) `PGPASSWORD` через env. Чище, не светит пароль в `ps auxf`.

Используй (б) — `PGPASSWORD: ${POSTGRES_PASSWORD}` в `environment:`.

### `pg_dump` флаги

- `--no-owner` — не пишет `OWNER TO` команды (восстановление в другой инстанс без проблем с user'ами).
- `--clean --if-exists` — генерирует `DROP TABLE IF EXISTS` перед `CREATE` (идемпотентное восстановление).
- `--no-privileges` — опционально, не пишет GRANT'ы (мы их и не используем — Settings создаёт схему через alembic).
- НЕ используй `--data-only` или `--schema-only` — нужен полный дамп.

### Volume vs bind-mount

Named volume `bb-db-backups` — изолирован от хоста, persistent. Bind-mount `./backups` тоже работает, но загромождает рабочую копию репо. **Используй named volume.** Если владельцу нужно скачать дамп — `docker run --rm -v bb-db-backups:/from -v $(pwd):/to alpine cp /from/<file> /to/`.

### Race с alembic migration

Если бэкап стартанёт в момент когда alembic применяет миграцию — теоретически возможна неконсистентность (хотя `pg_dump` использует MVCC snapshot). На практике для MVP — игнорируем (cron в 02:30 UTC, миграции применяются на старте сервиса утром при deploy). Если станет проблемой — добавим advisory lock-handshake.

### Restore-команда — `read` подтверждение

`make prod.backup.restore` ДОЛЖЕН требовать явное подтверждение (по аналогии с `make nuke` который ждёт ввода `NUKE`). Шаблон:

```makefile
prod.backup.restore: ## Восстановить дамп: make prod.backup.restore FILE=bettgbot-2026-05-25T02-30-00Z.sql.gz
	@if [ -z "$(FILE)" ]; then echo "Usage: make prod.backup.restore FILE=..."; exit 1; fi
	@printf "ВСЕ ТЕКУЩИЕ ДАННЫЕ В БД БУДУТ ЗАМЕНЕНЫ дампом '$(FILE)'. Введите 'RESTORE' для подтверждения: "; \
	read ans; \
	if [ "$$ans" = "RESTORE" ]; then \
		$(PROD_COMPOSE) exec -T db-backup sh -c 'gunzip -c /backups/$(FILE)' | $(PROD_COMPOSE) exec -T db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'; \
	else \
		echo "Отмена."; \
		exit 1; \
	fi
```

## Ссылки

- Compose prod: [`infra/docker-compose.prod.yml`](../../infra/docker-compose.prod.yml)
- Deploy spec: [`docs/07-deployment.md`](../../docs/07-deployment.md) (TASK-031 обновит подробно)
- PROJECT_STATUS план Этапа 4: [`state/PROJECT_STATUS.md`](../../state/PROJECT_STATUS.md)

## Что НЕ делать

- Не добавлять S3/offsite-бэкапы — это за MVP. Этап MVP — на одной VPS, бэкап в локальный volume + retention.
- Не настраивать алертинг (email/Slack) — за MVP. Логируем в `docker logs`, оператор смотрит руками.
- Не делать point-in-time recovery (WAL archiving) — за MVP. Suffice ежесуточный snapshot.

**Размер:** M (2-4 часа с тестированием).
