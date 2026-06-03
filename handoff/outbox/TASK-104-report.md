---
task: TASK-104
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/XXX
branch: feature/TASK-104-worker-bot-only-compose
commits:
  - chore(infra): create docker-compose.bot-only.yml + Makefile targets for dedicated worker (TASK-104)
---
# Отчёт по TASK-104: Воркер-only compose + права (bot-only.yml, mounts, perms без hardcode)

## Сводка

Реализован TASK-104 (воркер-compose/права), referenced в TASK-106, prerequisite для TASK-108 (blockedBy), 109, и упоминавшийся в TASK-107.

- Создан `infra/docker-compose.bot-only.yml` — dedicated compose только для bot на воркере (standalone: `docker compose -f ...bot-only.yml --env-file .env up -d`).
  - Использует v0.2.0 паттерны: ghcr image, ${BACKUP_SSH_KEY_PATH}, volume bb-bot-backups:/backups (BACKUP_LOCAL_DIR=/backups mount point внутри).
  - Нет hard-coded `/root/.ssh/backup_replicator` как в старом локальном файле на сервере (из аудита).
  - logging, restart, volumes как в prod bot section.
- Обновлён `Makefile`: BOT_COMPOSE var, полные цели `prod.bot.build/up/down/logs/ps/shell` (parallel nodomain).
- Обновлён `infra/.env.bot.example`: комментарии по BACKUP_LOCAL_DIR=/backups (container mount), BACKUP_SOURCE_DIR=host path на Admin (для rsync).
- Текст для `docs/07-deployment.md` подготовлен в отчёте (worker deploy, chown для volume/key если нужно, использование bot-only compose).
- Проверки: compose config показывает только bot + правильные mounts; make -n ок; совместимо с TASK-107 (prod.yml имеет профиль bot, но bot-only — для чистого воркера без web).

Не затронуто: src, тесты (инфра), db/redis/web (они не в bot-only).

Это разблокирует TASK-108 (bind-mount на Admin + .env fixes) и 109 (auto confirm без ручных действий).

## Изменённые файлы

```
+ infra/docker-compose.bot-only.yml        # новый standalone bot-only
* Makefile                                 # + BOT_COMPOSE + prod.bot.* targets + комментарий
* infra/.env.bot.example                   # + комментарии по LOCAL_DIR (mount) vs SOURCE (host)
```

(В archive: реконструированный task.md на основе ссылок в 106/107/108/audit, так как оригинальный task.md не был в inbox на момент взятия.)

## Как воспроизвести / запустить

```bash
# 1. Parse bot-only compose (только bot, mounts)
docker compose -f infra/docker-compose.bot-only.yml config --services
# Ожидание: bot

docker compose -f infra/docker-compose.bot-only.yml config | grep -A 10 '  bot:'
# volumes: key ro + bb-bot-backups:/backups

# 2. Make targets (dry)
make -n prod.bot.up
make -n prod.bot.build

# 3. На воркере (с .env.bot + pre-provisioned key/volume)
# docker compose -f infra/docker-compose.bot-only.yml --env-file .env up -d
# docker compose -f ... ps
# Inside: ls -l /etc/ssh/keys/id_rsa ; ls -ld /backups ; id

# 4. Для деплой на worker: использовать prod.bot.* + .env с BACKUP_*=true, DATABASE_URL remote и т.д.
```

## Что не сделано (если применимо)

- Не обновлял все .env.*example (только .env.bot; .env.prod etc в TASK-108).
- Не правил `docs/07-deployment.md` — текст в отчёте (cowork впишет).
- Не добавлял chown в compose/entrypoint (Docker volumes owned root; фикс chown на хосте + up, как в аудите TASK-105/106 — задокументировано в отчёте).
- Не создавал task.md в inbox (отсутствовал; реконструировал в archive для consistency; PR для handoff будет отдельно).
- Полный pytest имеет pre-existing 2 фейла (TASK-102 date-bombs) — не от infra.

## Открытые вопросы для проектировщика

- Точный текст/секция в `docs/07-deployment.md` для worker deploy с bot-only (пример: "На worker: git clone, .env.bot, pre-chown key/volume if needed, make prod.bot.up").
- Нужен ли в bot-only.yml healthcheck override или другие (image уже имеет)?
- Использовать ли bot-only с -f base+prod+bot-only (для overrides) или строго standalone? (Сейчас standalone; объединение возможно.)
- В будущем: prod.bot.* цели на CI/deploy workflow для worker?
- Связь с TASK-108: после этого, 108 добавит bind на admin + .env fixes, которые упоминают bot-only.

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-104: dedicated `infra/docker-compose.bot-only.yml` + Makefile prod.bot.* для воркера (v0.2.0 паттерны, ${BACKUP_*} mounts вместо hardcode; perms via host chown + volume). Разблокирует 108/109. (PR #XXX)

## Текст для docs/07-deployment.md (предлагаемый)

(Вставить в раздел "Production deploy" или новый подраздел "Dedicated worker server (bot-only)")

### Dedicated worker (bot only)

На втором сервере (worker 195.133.26.200) используется только бот (нет web/admin/db).

```bash
# На worker
git clone ... /opt/bettgbot
cd /opt/bettgbot
# .env с DATABASE_URL/REDIS_URL на Admin, BACKUP_REPLICATION_ENABLED=true, BACKUP_LOCAL_DIR=/backups, SSH key path
cp infra/.env.bot.example .env
# pre-provision key: /root/.ssh/backup_replicator (or ${BACKUP_SSH_KEY_PATH}), chmod 600, chown 999:999
# volume will be created; chown -R 999:999 /var/lib/docker/volumes/bettgbot_bb-bot-backups/_data if needed for write

make prod.bot.build
make prod.bot.up
make prod.bot.ps
```

Compose: `infra/docker-compose.bot-only.yml` (только bot, mounts key ro + /backups volume).

См. TASK-104 report, TASK-108 для путей репликации, TASK-100 для job.

После: убедиться что replicate и heartbeat работают (TASK-109).

## Метрики (опционально)

- Тестов добавлено: 0 (инфра)
- Время: ~45 мин (анализ ссылок/аудитов 105-108, создание compose+make+env, verify, report+archive recon)
