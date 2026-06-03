---
id: TASK-104
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: [TASK-103]
related:
  - handoff/outbox/backup-replication-deployment-audit-2026-06-03.md
  - infra/Dockerfile.bot
  - infra/docker-compose.prod.yml
priority: high
estimate: M
---

# TASK-104: Воркерный bot-compose в репозитории + владение ключом/volume репликации

## Контекст

Деплой-аудит 2026-06-03 (PR #214): воркер-сервер запускает **локальный** `docker-compose.bot-only.yml`, которого нет в репо в актуальном виде — он хардкодит mount ключа (`/root/.ssh/backup_replicator:...`) вместо v0.2.0-паттерна `${BACKUP_SSH_KEY_PATH}`, и не повторяет volume/env для репликации из `prod.yml`. Плюс репликация падала по правам: SSH-ключ и `/backups`-volume принадлежали root, а процесс в контейнере — `bb` (uid 999) → `R_OK=False` на ключе, `W_OK=False` на `/backups` (`rsync`/`mkdir` падали с PermissionError). Деплой-команда руками сделала `chown 999:999` ключа и volume — но в образе/репо этого нет, при пересоздании сломается снова.

## Цель

Дать в репозитории воспроизводимый воркерный запуск (только сервис `bot`) под split-топологию v0.2.0, с корректным владением ключом и каталогом репликации — без ручных `chown` на сервере.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-104-report.md`.

- [ ] `infra/docker-compose.bot-only.yml` (committed): поднимает **только** `bot` на воркере. `DATABASE_URL`/`REDIS_URL` → публичный IP Admin (из env), backup-volume `bb-bot-backups:/backups`, SSH-ключ через `${BACKUP_SSH_KEY_PATH}:<path>:ro`, и env репликации (`BACKUP_REPLICATION_ENABLED`, `BACKUP_SOURCE_HOST/SSH_USER/SOURCE_DIR/LOCAL_DIR`). Никаких хардкод-путей.
- [ ] **Владение ключом/каталогом** без ручного chown на хосте — выбери и реализуй один путь, обоснуй в отчёте:
  - (a) entrypoint-обёртка в `infra/Dockerfile.bot`, которая при старте `chown bb:bb`/`chmod 600` примонтированного ключа и `chown bb` `/backups` (требует старта от root до `gosu`/`su-exec` → drop до bb); **или**
  - (b) init-контейнер/`command`-хук в bot-only compose, делающий chown до запуска бота; **или**
  - (c) если меняем uid — задокументировать.
  - Цель: после `compose up` ключ читается, `/backups` пишется от bb (uid 999) без ручных действий.
- [ ] Хелпер `_run_rsync_pull` (TASK-100): убедиться, что путь к ключу берётся из `BACKUP_SSH_KEY_PATH` (а не хардкод), и при недоступном/непрочитанном ключе — внятный warning, без падения джоба.
- [ ] Текст раздела «Воркер-сервер (репликация)» для `docs/07-deployment.md` — **в отчёт** (doc впишет cowork): как примонтировать ключ, какие env, проверка `replicate_latest_backup` (появление файлов в `/backups`, `backup_run.replicated_at` проставлен).
- [ ] `ruff`/`mypy`/`pytest` зелёные; PR, отчёт, move inbox→archive, rebase на свежий main, явный auto-merge.

## Артефакты
```
+ infra/docker-compose.bot-only.yml
* infra/Dockerfile.bot                   (если путь (a) — entrypoint chown)
* src/bot/scheduler/jobs.py              (только если ключ-путь не из env — проверить)
```

## Подсказки / границы
- Не публиковать ключ/секреты в репо. `chown` в образе — только над **примонтированным** ключом, сам ключ остаётся на хосте.
- `blockedBy: TASK-103` — воркеру нужен сетевой доступ к БД (порты) раньше, чем чинить репликацию-волюм; и обе задачи трогают деплой-доку.
- `docs/`/`state/` не редактировать — зона cowork.

## Ссылки
- Аудит: [`handoff/outbox/backup-replication-deployment-audit-2026-06-03.md`](../outbox/backup-replication-deployment-audit-2026-06-03.md)
- Репликация: TASK-100 (`replicate_latest_backup`, `_run_rsync_pull`)
