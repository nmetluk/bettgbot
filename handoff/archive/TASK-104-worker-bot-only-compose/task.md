---
id: TASK-104
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/TASK-106-report.md
  - handoff/inbox/TASK-108-replication-paths-permanent.md
  - infra/docker-compose.prod.yml
  - infra/docker-compose.bot-only.yml
priority: high
estimate: S
---

# TASK-104: Воркер-only compose + права (bot-only.yml, mounts, perms без hardcode)

## Контекст

Прод-диагностика (TASK-105/106) выявила:
- На воркере использовался старый локальный `docker-compose.bot-only.yml` с hard-coded монтом `/root/.ssh/backup_replicator:...` (не v0.2.0 паттерны с `${BACKUP_SSH_KEY_PATH}`).
- Проблемы прав: ключ и volume `/backups` owned root на хосте, внутри контейнера bb (uid=999) не мог читать/писать (R_OK/W_OK=False). Фиксили chown 999:999 на хосте + restart.
- Bot-only compose не обновлён под v0.2.0 (TASK-027+).

TASK-107 убрал бот с Admin (только на воркере).
TASK-108 (blockedBy 104) требует bot-only для правильного mount /backups (BACKUP_LOCAL_DIR=/backups внутри контейнера) и обновления .env.
TASK-109 требует после 104+107+108.

Нужен постоянный repo-фикс: официальный `infra/docker-compose.bot-only.yml` в репо, без hardcode, с правильными volume/mount для key и backups, чтобы perms работали после деплоя (с chown в deploy docs).

## Цель

На dedicated worker сервере поднимается только `bot` (через bot-only compose), с правильными mounts `${BACKUP_SSH_KEY_PATH}` и volume `bb-bot-backups:/backups` (LOCAL_DIR=/backups), без hard-coded путей, используя паттерны из prod.yml.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — `handoff/outbox/TASK-104-report.md`.

- [ ] Создан `infra/docker-compose.bot-only.yml` (standalone для воркера; image из ghcr, restart, logging, volumes с ${BACKUP_SSH_KEY_PATH}:/etc/ssh/keys/id_rsa:ro и bb-bot-backups:/backups; следует v0.2.0 паттернам, без hardcode как /root/.ssh/...).
- [ ] Обновлён `Makefile`: BOT_COMPOSE var, цели prod.bot.build/up/down/logs/ps/shell (аналог nodomain).
- [ ] Обновлены примеры `.env.bot.example` (комментарии BACKUP_LOCAL_DIR=/backups как container mount point, SOURCE как host path на Admin; см. TASK-108).
- [ ] Текст для `docs/07-deployment.md` (в отчёт): как деплоить на воркер (bot-only compose + .env.bot + chown для key/volume если нужно, firewall на Admin).
- [ ] Проверка: `docker compose -f infra/docker-compose.bot-only.yml config --services` = только bot; volumes/mounts корректны; make -n prod.bot.* ок.
- [ ] `ruff`/`mypy`/`pytest` зелёные (только инфра); PR, отчёт, move inbox→archive, rebase на свежий main, явный auto-merge.
- [ ] Совместимо с TASK-107 (профиль bot в prod.yml) и разблокирует 108/109.

## Артефакты

```
+ infra/docker-compose.bot-only.yml        # новый, dedicated bot-only
* Makefile                                 # BOT_COMPOSE + prod.bot.* targets
* infra/.env.bot.example                   # комментарии по LOCAL_DIR/SOURCE (mount vs host)
```

## Ссылки

- Диагностика/фиксы ops: [`handoff/outbox/TASK-106-report.md`](../outbox/TASK-106-report.md), [`handoff/outbox/backup-replication-deployment-audit-2026-06-03.md`](../outbox/backup-replication-deployment-audit-2026-06-03.md)
- Бот только на воркере: TASK-107
- Репликация пути: TASK-108 (blockedBy 104), TASK-100
- Подсказки: в compose использовать ${} vars, не хардкод; perms — chown на хосте для named volume _data (999:999 = bb uid)

## Подсказки исполнителю

- bot-only.yml standalone (только bot service) — на воркере `docker compose -f ...bot-only.yml --env-file .env up -d` (DB/REDIS remote по URL в .env).
- Объединять с base+prod можно, но для чистого воркера — только bot-only.
- Не трогать src/, только infra/Makefile/examples.
- Права: compose не чинит chown (Docker volume owned root), фикс в deploy (chown + docker compose up) — задокументировать.
