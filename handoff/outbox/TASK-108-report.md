---
task: TASK-108
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/228
branch: feature/TASK-108-replication-paths-permanent
commits:
  - chore(infra): permanent replication paths (bind on Admin, /backups mount on worker) (TASK-108)
---
# Отчёт по TASK-108: Постоянные пути репликации (Admin source bind-mount + worker LOCAL_DIR=/backups)

## Сводка

Выполнен постоянный repo-фикс для репликации (TASK-100 job), чтобы не нужны были ручные симлинки и .env правки после ребилда (как в TASK-106 ops).

- В `infra/docker-compose.prod.yml` (и no-domain): для db-backup добавлен bind-mount `- /opt/backups/bettgbot/db:/backups` вместо (или вместо named) volume. Дампы теперь пишутся напрямую на хостовый путь, доступный для rsync/ssh с worker без symlinks. Named volume bb-db-backups оставлен в volumes list для совместимости (если старые контейнеры/volume data).
- Обновлён `infra/docker-compose.bot-only.yml`: добавлен BACKUP_LOCAL_DIR: /backups в environment (документирует, что это container mount point, не host path; volume bb-bot-backups:/backups уже был).
- Обновлены `.env.*example` (example, prod, bot): BACKUP_SOURCE_DIR и LOCAL_DIR с комментариями (SOURCE = host path на Admin /opt/... , LOCAL = /backups в контейнере). .env.bot уже был частично обновлён в TASK-104, синхронизировано.
- Текст для `docs/07-deployment.md` подготовлен ниже (итоговые пути, кто монтирует, проверка replicate без ручного).

Решение по bb-db-backups: оставил в volumes для compat (не удалил), но основной mount теперь bind на explicit host path (как рекомендовано в задаче "вместо/вдобавок"). Это делает источник стабильным, volume может использоваться параллельно если нужно (но /backups теперь bind).

Обоснование: bind даёт предсказуемый хостовый путь для ssh-юзера на Admin, без зависимости от docker volume internals (/var/lib/docker/.../_data), который ломался при volume recreate. Host path /opt/... легко бэкапить, rsync'ить, chown'ить.

## Изменённые файлы

```
* infra/docker-compose.prod.yml            # db-backup: bind /opt/backups/bettgbot/db:/backups + комментарий TASK-108
* infra/docker-compose.prod-no-domain.yml  # аналог для no-domain (если применимо)
* infra/docker-compose.bot-only.yml        # + BACKUP_LOCAL_DIR: /backups в env (документация)
* infra/.env.example                       # SOURCE/LOCAL с комментариями (host vs container)
* infra/.env.prod.example                  # то же
* infra/.env.bot.example                   # синхронизация комментариев (уже было частично из 104)
```

## Как воспроизвести / запустить

```bash
# 1. Проверить compose (bind на Admin, volume на worker)
POSTGRES_USER=... POSTGRES_PASSWORD=... ... ADMIN_DOMAIN=... \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config | \
  sed -n '/^  db-backup:/,/^  certbot:/p' | grep -E 'volumes:|/opt/backups'

# Для worker:
docker compose -f infra/docker-compose.bot-only.yml config | grep -A5 '  bot:' | grep -E 'BACKUP_LOCAL_DIR|volumes:'

# 2. Make / deploy (после .env setup)
# На Admin: make prod.up (или nodomain) — dumps будут в /opt/backups/bettgbot/db на хосте
# На worker: make prod.bot.up — /backups inside = volume, LOCAL_DIR=/backups

# 3. Проверить replicate (после backup success на Admin)
# На worker bot:
docker exec bettgbot-bot-1 python -m src.bot.scheduler.jobs replicate_latest_backup --once
# Или ждать cron 15m.
# Проверить: ls /backups/*.sql.gz inside bot; psql на Admin: select * from backup_run where replicated_at is not null;

# 4. docker compose config везде (как в конвенциях)
docker compose -f ... config | grep BACKUP_SOURCE_DIR  # etc
```

## Что не сделано (если применимо)

- Не удалил named volume bb-db-backups полностью (оставил в list для compat, как "оставить как есть").
- Не обновлял runbook-dr.md или другие docs (только текст в отчёт для 07-deployment).
- Не добавил создание /opt/backups/... в Makefile/deploy scripts (предполагается в deploy docs, как /opt/bettgbot).
- Не трогал src/ (только infra, per DoD).
- Полный pytest: 2 pre-existing фейла в analytics (TASK-102 date-bombs) — не от infra; остальное зелёное. ruff/format/mypy зелёные (no src change).

## Открытые вопросы для проектировщика

- Подтвердить: /opt/backups/bettgbot/db должен создаваться на Admin хосте в deploy (mkdir -p, chown root:root или для ssh user)? Добавить в make prod.* или docs?
- Для no-domain: bind применим? (да, если bootstrap VPS выступает как Admin).
- Если нужно параллельно использовать named volume bb-db-backups (для локального backup на Admin?), то bind + volume? Но target /backups один, bind выигрывает. Если нужно оба, можно mount subdir, но для dumps — bind достаточно.
- Текст в docs/07-deployment.md — вставить куда именно (после offsite backup шага)?

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-108: постоянные пути репликации (bind-mount /opt/backups/bettgbot/db на Admin для db-backup; /backups volume + LOCAL_DIR=/backups на worker в bot-only; обновлены .env примеры). dumps на хосте без symlinks, replicate из коробки. (PR #228)

## Текст для docs/07-deployment.md (предлагаемый для вставки, впишет cowork)

(Добавить после раздела про offsite backup, перед "Переход на полноценный прод", или как новый подраздел в Шаг 6 или отдельно после backups.)

### Replication paths (TASK-108, TASK-100)

Для `replicate_latest_backup` (бот на worker тянет дампы с Admin по rsync/ssh) пути должны быть стабильными после ребилда контейнеров:

**На Admin (в `docker-compose.prod.yml` и no-domain):**
- db-backup пишет дампы в bind-mount: `- /opt/backups/bettgbot/db:/backups`
- Дампы доступны на хосте по пути `/opt/backups/bettgbot/db/*.sql.gz` (для ssh-юзера root с worker).
- Создайте путь на хосте: `mkdir -p /opt/backups/bettgbot/db` (в deploy скриптах или manually).
- Named volume `bb-db-backups` оставлен в compose для совместимости (но основной — bind).

**На worker (в `docker-compose.bot-only.yml` + .env):**
- Volume: `bb-bot-backups:/backups` (mount point внутри контейнера).
- `BACKUP_LOCAL_DIR=/backups` (в .env.bot и дефолт в compose).
- `BACKUP_SOURCE_DIR=/opt/backups/bettgbot/db` (хостовый путь на Admin, в .env).
- SSH ключ: mount `${BACKUP_SSH_KEY_PATH}:/etc/ssh/keys/id_rsa:ro` (pre-provisioned, perms 600, chown 999:999 на хосте для bb uid).

**Проверка (после success backup на Admin):**
```bash
# На worker bot:
docker exec <bot> ls -l /backups/*.sql.gz
# Должен скопироваться свежий.
# В БД (на Admin или worker psql):
SELECT id, filename, replicated_at FROM backup_run ORDER BY id DESC LIMIT 3;
# replicated_at должен проставиться джобом.
```

См. `infra/.env.*example`, compose файлы, TASK-100 job `_run_rsync_pull`, TASK-104 (bot-only), TASK-108 report.

Это устраняет ручные `ln -s` и правки .env из аудитов.

## Метрики (опционально)

- Тестов: 0 (инфра)
- Время: ~1ч (анализ, edits compose+env+bot-only, verify, report)
