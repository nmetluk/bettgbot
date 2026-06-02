---
id: TASK-100
created: 2026-06-01
author: cowork-agent
parallel-safe: false
blockedBy: [TASK-099]
related:
  - handoff/inbox/TASK-099-backup-health-heartbeat.md
  - handoff/outbox/operational-backup-heartbeat-proposal.md
  - docs/07-deployment.md
priority: normal
estimate: M
---

# TASK-100: Репликация бэкапа на сервер с ботом (pull по SSH)

## Контекст

Дамп БД создаётся контейнером `db-backup` на сервере админки/БД (Admin). Нужна вторая копия на сервере с ботом — на случай потери Admin-сервера. Зависит от TASK-099: таблица `backup_run` уже содержит `filename` и `replicated_at` (колонки заведены миграцией 0008 в TASK-099); эта задача их **заполняет**.

**Модель — pull:** бот (на Bot-сервере) тянет свежий дамп с Admin-сервера. Адрес Admin-сервера берём из настроек проекта (есть `ADMIN_DOMAIN`; в no-domain-проде — IP). SSH-ключи между серверами **уже есть** (деплой-предпосылка) — задача их **не provision'ит**, только использует путь к ключу из настроек.

Решение зафиксировано в [`state/DECISIONS.md`](../../state/DECISIONS.md) (2026-06-01, строка про репликацию). Почему pull, а не push: пуллеру (боту) достаточно знать адрес источника (Admin) — он уже в настройках; push потребовал бы хранить адрес Bot-сервера в конфиге Admin. Почему в боте, а не внешним cron: тот же урок, что в TASK-099 — внешние shell-скрипты теряются; держим в репозитории, версионируемо и тестируемо (rsync вызывается из джоба как subprocess, оркестрация и логирование — в Python).

## Цель

Bot-джоб `replicate_latest_backup`: периодически тянет новейший непрореплицированный дамп с Admin-сервера по SSH (`rsync`), кладёт в локальный каталог на Bot-сервере, проставляет `backup_run.replicated_at`. Heartbeat (TASK-099) после этого показывает «реплицирован ✓».

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-100-report.md`.

- [ ] `BackupSettings` (расширить существующую группу из TASK-039): `replication_enabled: bool` (`BACKUP_REPLICATION_ENABLED`, default `false`); `source_host: str | None` (`BACKUP_SOURCE_HOST`, default — из `ADMIN_DOMAIN`/деплой-конфига); `source_ssh_user: str` (`BACKUP_SSH_USER`); `ssh_key_path: Path` (`BACKUP_SSH_KEY_PATH`); `source_dir: str` (`BACKUP_SOURCE_DIR`, удалённый каталог дампов); `local_dir: Path` (`BACKUP_LOCAL_DIR`, куда класть на Bot-сервере). При `replication_enabled=true` валидировать, что заданы host/user/key/source_dir/local_dir.
- [ ] `BackupRunRepository`: `get_last_unreplicated_success()` (последний `success` с `replicated_at IS NULL`), `mark_replicated(id, ts)`.
- [ ] Хелпер `replicate_backup_file(...)`: `rsync -az -e "ssh -i <key> -o StrictHostKeyChecking=accept-new" <user>@<host>:<source_dir>/<filename> <local_dir>/` через `asyncio`-subprocess; таймаут; ненулевой код возврата → ошибка с stderr (без утечки ключа в лог). Идемпотентно (rsync не перекачивает, если файл уже на месте).
- [ ] Джоб `replicate_latest_backup(*, session_maker)` в `jobs.py`: если `replication_enabled=false` → не регистрируется. Иначе: взять последний непрореплицированный `success` (нужен `filename`), `rsync`-pull, при успехе `mark_replicated(now())`. Ошибка → `warning` (heartbeat в TASK-099 покажет «не реплицирован»; алерт по просрочке репликации — здесь же добавить порог `BACKUP_REPLICATION_MAX_LAG_HOURS`, default 3, в heartbeat-сводку).
- [ ] Регистрация в `builder.py` при `replication_enabled`: `IntervalTrigger(minutes=15)`, `id="replicate_latest_backup"`, `coalesce=True`, `max_instances=1`, `misfire_grace_time` ~600. Включаем на **Bot-сервере** (где есть SSH-доступ к Admin).
- [ ] Инфра: в образ бота добавить `rsync` + `openssh-client` (`infra/Dockerfile.bot`); смонтировать SSH-ключ read-only и `local_dir` (volume) в сервис `bot`; env-переменные в `.env.*example` + сервис `bot` в prod-compose (по умолчанию репликация выключена). known_hosts/`accept-new` — задокументировать.
- [ ] Heartbeat (TASK-099) расширить: статус репликации последнего бэкапа → алерт, если последний `success` не реплицирован дольше `BACKUP_REPLICATION_MAX_LAG_HOURS`.
- [ ] Тесты: `BackupRunRepository.get_last_unreplicated_success`/`mark_replicated` (integration); джоб с замоканным rsync-subprocess — успех → `replicated_at` проставлен; ошибка rsync → не проставлен, `warning`; `replication_enabled=false` → джоб не зарегистрирован (`test_builder`); парсинг/валидация настроек репликации.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные. PR `TASK-100: backup replication to bot`; отчёт; move inbox→archive; ветка отребейзена на свежий `main`.

## Артефакты

```
* src/shared/config.py                       # BackupSettings: replication_* поля
* src/shared/repositories/backup_run.py      # get_last_unreplicated_success / mark_replicated
+ src/bot/_backup_replication.py (или в jobs) # rsync-pull хелпер
* src/bot/scheduler/jobs.py                  # replicate_latest_backup
* src/bot/scheduler/builder.py               # условная регистрация
* infra/Dockerfile.bot                       # + rsync, openssh-client
* infra/docker-compose.prod*.yml, .env.*example  # env + mount ключа/local_dir
+ tests/...
```

## Ссылки

- Зависимость: [TASK-099](TASK-099-backup-health-heartbeat.md) (таблица `backup_run`, колонки `filename`/`replicated_at`)
- Proposal: [`handoff/outbox/operational-backup-heartbeat-proposal.md`](../outbox/operational-backup-heartbeat-proposal.md)
- Адрес источника: env `ADMIN_DOMAIN` (`infra/.env.*example`)

## Подсказки / границы

- SSH-ключи между серверами — **деплой-предпосылка** (владелец обеспечивает); задача только использует `BACKUP_SSH_KEY_PATH`. Ключ не коммитить, не логировать.
- Не тянуть весь каталог при каждом тике — только последний непрореплицированный файл по `backup_run.filename`. (rsync всё равно идемпотентен.)
- Ротацию локальных копий на Bot-сервере (удаление старых) можно сделать здесь же простым `find -mtime` или вынести в backlog — на твоё усмотрение, отметь в отчёте.
- `docs/`/`state/` не трогать — обновит cowork.
