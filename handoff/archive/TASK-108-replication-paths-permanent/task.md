---
id: TASK-108
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: [TASK-104]
related:
  - handoff/outbox/TASK-106-report.md
  - infra/docker-compose.prod.yml
  - infra/docker-compose.bot-only.yml
priority: high
estimate: S
---

# TASK-108: Постоянные пути репликации (Admin source bind-mount + worker LOCAL_DIR=/backups)

## Контекст

Прод-диагностика TASK-106 (отчёт `handoff/outbox/TASK-106-report.md`) показала, что репликация падала из-за **двух конфиг/инфра-ошибок путей**, которые сейчас закрыты хрупкими ручными костылями на серверах:

1. **`BACKUP_LOCAL_DIR` на воркере был хостовым путём** (`/opt/...`) вместо точки монтирования backup-volume **внутри контейнера** (`/backups`) → джоб писал «мимо», `ls /backups` = total 0. Исполнитель поправил `.env` руками.
2. **Источник дампов на Admin недоступен ssh-источнику.** Дампы пишутся в docker-volume `bb-db-backups`, а `BACKUP_SOURCE_DIR` (ssh rsync source) указывал на хостовый `/opt/backups/bettgbot/db`, который **пуст**. Исполнитель сделал `ln -s /var/lib/docker/volumes/bettgbot_bb-db-backups/_data /opt/backups/bettgbot/db` — работает, но **ломается при пересоздании volume**.

Нужен постоянный фикс в репозитории, чтобы после ребилда/пересоздания контейнеров репликация работала без ручных симлинков и правок `.env`.

## Цель

`replicate_latest_backup` (TASK-100) работает «из коробки» после деплоя: источник на Admin — стабильный хостовый путь, `BACKUP_LOCAL_DIR` на воркере = точка монтирования в контейнере.

## Definition of Done

> 🚨 Перед archive — `handoff/outbox/TASK-108-report.md`.

- [ ] **Admin (db-backup):** в `infra/docker-compose.prod.yml` (и no-domain, если применимо) добавить **bind-mount** вывода дампов на стабильный хостовый путь, доступный ssh-источнику репликации — напр. `- /opt/backups/bettgbot/db:/backups` для сервиса `db-backup` (вместо/вдобавок к named-volume). Чтобы файлы реально лежали на хосте, а не только в анонимном volume. Решить судьбу `bb-db-backups` (оставить как есть для совместимости или заменить bind) — обосновать в отчёте.
- [ ] **Worker (.env/compose):** `BACKUP_LOCAL_DIR` по умолчанию = **`/backups`** (точка монтирования backup-volume в контейнере), а не хостовый путь. Поправить `infra/.env.*example` и `infra/docker-compose.bot-only.yml` (TASK-104), убрать возможность спутать host vs container path; коротко задокументировать.
- [ ] `BACKUP_SOURCE_DIR` (на воркере, удалённый путь источника) = хостовый путь Admin из п.1 (напр. `/opt/backups/bettgbot/db`) — синхронизировать дефолты/комментарии в env-примерах.
- [ ] Текст для `docs/07-deployment.md` (в отчёт): итоговые пути источника/назначения, кто куда монтируется, проверка что `replicate_latest_backup` сам (без ручного rsync) копирует файл и проставляет `backup_run.replicated_at`.
- [ ] `ruff`/`mypy`/`pytest` зелёные (инфра, кода не трогает); PR, отчёт, move inbox→archive, rebase на свежий main, явный auto-merge.

## Артефакты
```
* infra/docker-compose.prod.yml            (db-backup: bind-mount вывода на host)
* infra/docker-compose.bot-only.yml        (worker LOCAL_DIR / backup-volume mount) — связано с TASK-104
* infra/.env.example, .env.prod.example, .env.bot.example  (BACKUP_LOCAL_DIR=/backups, BACKUP_SOURCE_DIR=...)
```

## Подсказки / границы
- `BACKUP_LOCAL_DIR` — это путь **внутри контейнера** бота (mount point), не хостовый. То же различие для источника: ssh видит **хостовый** путь Admin.
- Не хардкодить секреты/ключи. `docs/`/`state/` не редактировать — текст в отчёт, впишет cowork.
- `blockedBy: TASK-104` — общий воркерный compose/volume.

## Ссылки
- Диагностика: [`handoff/outbox/TASK-106-report.md`](../outbox/TASK-106-report.md) (раздел «Ops-фиксы применённые»)
- Репликация: TASK-100 (`replicate_latest_backup`, `_run_rsync_pull`)
