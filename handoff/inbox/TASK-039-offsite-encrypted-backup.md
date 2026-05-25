---
id: TASK-039
created: 2026-05-25
author: external-auditor
parallel-safe: true
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: L
---

# TASK-039: Offsite encrypted backup БД (rclone + age) + weekly restore-smoke

## Контекст

Аудит MVP 2026-05-25, находка **C-07 (Critical)**. Текущий `db-backup` сервис делает `pg_dump | gzip` в named-volume `bb-db-backups` на том же VPS. `scripts/backup-to-drive.sh` копирует только handoff/state/sessions, БД не трогает. Если VPS физически потерян — все данные потеряны. Шифрования-at-rest нет. Бэкап не проверяется restore-тестом.

## Цель

1. Ежедневный шифрованный push pg_dump в S3-совместимое хранилище (B2/S3/GDrive через rclone) c использованием age для шифрования.
2. Еженедельный smoke-restore в одноразовый Postgres-контейнер с базовой проверкой row counts.
3. DR-runbook (отдельная задача TASK-042; здесь — только бэкап).

## Definition of Done

- [ ] `Settings` имеет новый раздел `BackupSettings` (env prefix `BACKUP_`):
  - `enabled: bool = False` (включается в prod явно)
  - `age_recipient: str | None` (публичный ключ age для шифрования; private хранится у владельца **вне VPS**)
  - `rclone_remote: str | None` (например `b2:bettgbot-backups`)
  - `retention_days: PositiveInt = 30`
- [ ] `infra/Dockerfile.db-backup` (новый) на базе `postgres:16-alpine` + установленные `rclone` и `age` (через apk).
- [ ] `infra/docker-compose.prod.yml` `db-backup` использует новый Dockerfile, command делает:
  ```sh
  pg_dump ... | gzip | age -r ${AGE_RECIPIENT} > /tmp/dump.sql.gz.age
  rclone copy /tmp/dump.sql.gz.age ${RCLONE_REMOTE}/$(date -u +%FT%H-%M-%SZ)/
  rclone delete --min-age ${RETENTION_DAYS}d ${RCLONE_REMOTE}/  # cleanup
  ```
- [ ] Rclone config монтируется как docker secret (mode 0400) либо через `RCLONE_CONFIG_*` env.
- [ ] Cron-base scheduler (Ofelia/supercronic) вместо текущего sleep-loop — `30 2 * * *`.
- [ ] Новый Makefile-цель `make prod.backup.verify` — pulls последний дамп, восстанавливает в одноразовый Postgres контейнер, делает `SELECT COUNT(*)` по 3 ключевым таблицам (`user`, `event`, `prediction`), удаляет контейнер.
- [ ] GitHub Actions workflow `.github/workflows/backup-verify.yml` (weekly schedule) запускает `make prod.backup.verify` на VPS через ssh (или secret-based runner) — fails если smoke не зелёный.
- [ ] `docs/07-deployment.md` обновлён:
  - Шаг «Сгенерировать age-ключевую пару, private сохранить в keychain владельца».
  - Шаг «Настроить rclone config».
  - Шаг «Включить `BACKUP_ENABLED=true`».
  - Раздел «Восстановление в DR-сценарии» (заглушка, заполняется в TASK-042).
- [ ] Local Makefile добавляет `prod.backup.restore.offsite FILE=<remote-path>` — pulls + decrypts + restores.
- [ ] PR в GitHub, имя `TASK-039: offsite encrypted backup with weekly verify`.
- [ ] Отчёт в `handoff/outbox/TASK-039-report.md` с описанием выбранного провайдера хранилища (выбор остаётся на владельца) и стоимости.
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `* src/shared/config.py` — `BackupSettings`
- `+ infra/Dockerfile.db-backup` — новый
- `* infra/docker-compose.prod.yml` — db-backup перепрошит, cron-scheduler
- `* Makefile` — `prod.backup.verify`, `prod.backup.restore.offsite`
- `+ .github/workflows/backup-verify.yml` — weekly verify
- `* docs/07-deployment.md` — backup setup
- `* infra/.env.example` + `infra/.env.prod.example` — `BACKUP_*` переменные

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-07
- age: https://github.com/FiloSottile/age
- rclone B2: https://rclone.org/b2/
- 3-2-1 backup rule: https://www.veeam.com/blog/321-backup-rule.html

## Подсказки

- Стоимость: Backblaze B2 ~$6/TB/month; реалистично для проекта <$1/month.
- age-keypair `age-keygen -o key.txt` → public в env, private у владельца.
- Сначала проверь, есть ли у владельца предпочтение по хранилищу — если есть готовый S3, скип B2.
- `apk add --no-cache rclone age` в Dockerfile добавит ~30 MB к образу — приемлемо.
- Для теста локально можно использовать `rclone mkdir local-test:/tmp/bb-backups-test` (filesystem backend) — без необходимости в реальном S3.
- Restore-smoke в новый одноразовый контейнер: `docker run --rm -v <volume>:/data postgres:16 sh -c '...'` либо через `docker compose run --rm -it ...`.
