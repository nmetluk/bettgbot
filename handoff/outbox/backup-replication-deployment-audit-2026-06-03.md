## Operational: Backup & Replication Deployment Audit and Fixes (2026-06-03)

**Date:** 2026-06-03
**Author:** local agent (via tools)
**Context:** Follow-up after updating servers to v0.2.0 release. User requested check of backups/replication, fix deployment issues *without modifying project source code* (src/, Dockerfiles, committed compose ymls etc. — those go to architect for urgent fixes). Write findings to file per handoff rules, transmit to GitHub repo. Also send test message to admin channel (user never received before). Deployment errors must be resolved by end of this.

## What was found (pre-fix checks on live servers post v0.2.0 update)

### Backups (dumps)
- Hourly dumps **working**: files like bettgbot-2026-06-03T19-14-04Z.sql.gz etc. created in volume `bettgbot_bb-db-backups`.
- `db-backup` container running local-only loop (BACKUP_ENABLED=false), logs show "✓ Local backup successful".
- But `backup_run` table: all recent rows stuck in `status=running`, no `finished_at`, `filename`, `size_bytes`, `replicated_at`.
- Root cause (in running image): `start_backup_run` in baked script uses `psql -t -c "INSERT ... RETURNING id;" | tr -d '[:space:]'` → polluted ID like "13INSERT01", UPDATE fails with "trailing junk after numeric literal". (This is code-level, left for architect.)

### Replication
- No files appeared in `/opt/backups/bettgbot/db/` on Bot server (ls empty).
- Jobs registered on worker bot restart (`replicate_latest_backup`, `send_backup_health_heartbeat`).
- But:
  - SSH key `/root/.ssh/backup_replicator` mounted 600 root:root (or systemd-coredump 999 on host); inside container (bb uid=999) `R_OK=False` initially.
  - `/backups` volume (bb-bot-backups) owned root on host → not writable by bb (`W_OK=False`).
  - `local_dir.mkdir` and rsync in job would fail with PermissionError.
- Bot-only compose on worker server is old local file (hard-coded mount `/root/.ssh/backup_replicator:...`), not using v0.2.0 prod.yml patterns with `${BACKUP_SSH_KEY_PATH}`.
- DB/Redis unreachable from worker: `Connection refused` to 5.188.88.78:5432/6379 (even after code update).
- `docker port` on Admin: `5432/tcp -> None`. Ports **never published** in the prod compose used (only in dev override.yml to 127.0.0.1). Firewall DOCKER-USER rules for 195.133.26.200 existed and were re-applied, but useless without publish.
- This also breaks *all* DB-dependent jobs on worker (reminders, event results, etc. — logs full of ConnectionRefused).

### Heartbeat / notifications to admin channel
- Jobs registered on restarts.
- No observed executions/sends in logs (restarts around 19:14-19:19; cron minute=7).
- No `ops:last_backup` in redis.
- User confirmed: "я ни разу не получил сообщение в админский канал".
- Direct sends from VPS often blocked by provider (as documented in pinbetting.txt); main path is pending spool + send-pending-alerts.sh from control.

### Other deployment state
- Git on both servers updated to v0.2.0 (ac3d269), images rebuilt with generate_build_info (commit/tag correct in build_info inside containers).
- .env flags correct per architect quote (including on bot .env).
- Containers up post-update (bot often "healthy" or starting).
- Old cron removed long ago.
- `docker-compose.bot-only.yml` on worker not updated (local, pre-v0.2.0).

### Ports / connectivity root cause
- Architecture (pinbetting.txt + TASK-100) requires dedicated worker on second server to reach Admin DB/Redis over public IP + firewall whitelist.
- But committed `infra/docker-compose.prod.yml` (and no-domain) only have `restart: always` for db/redis — no `ports:`. (Dev-only in override.)
- Result: worker bot completely non-functional for anything needing DB.

## Deployment fixes applied (NO changes to project source code in repo)

All fixes done via server-side ops only (chown, temp non-git files, compose CLI overrides with /tmp yml, scripts, restarts). Source checkouts on servers and local /home/nm/bettgbot untouched for src/Docker/infra/*.yml etc.

### 1. Replication key & volume perms (Bot server 195.133.26.200)
- `chown 999:999 /root/.ssh/backup_replicator` (numeric; host uid 999 maps to container bb).
- `chown -R 999:999 /var/lib/docker/volumes/bettgbot_bb-bot-backups/_data` (for /backups inside).
- `docker compose -f docker-compose.bot-only.yml --env-file .env up -d bot` (remount).
- Verify inside: key owned by bb, R_OK=True; /backups W_OK=True (was False).
- (Note: bot-only.yml remains old hard-coded; perms now make it work.)

### 2. DB/Redis ports published (Admin server 5.188.88.78)
- Created **/tmp/db-ports-override.yml** (pure temp, not in git tree, not committed):
  ```yaml
  services:
    db:
      ports: ["5432:5432"]
    redis:
      ports: ["6379:6379"]
  ```
- Ran: `docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f /tmp/db-ports-override.yml up -d db redis`
- Result: `docker port bettgbot-db-1` now shows 5432/tcp -> 0.0.0.0:5432 (and 6379).
- Re-ran `/opt/bettgbot/bettgbot/scripts/apply-bot-firewall.sh` (or equiv); DOCKER-USER rules confirmed for 195.133.26.200.
- Verify from worker bot container: TCP to 5.188.88.78:5432 and :6379 now **OK**.
- (Ports will persist on current containers; for future recreates, include the /tmp override or equivalent in compose command. No project yml edited.)

### 3. Firewall / other
- Firewall re-applied.
- No other source changes.

### 4. Test message to admin channel
- Created pending spool on Admin: `/var/run/bettgbot-alerts/pending-alerts.txt` with INFO|Test Deploy|TEST MESSAGE ... verifying channel -1003795574407.
- On control: extracted token to ~/.bettgbot/telegram_bot_token (and exported), ran `/home/nm/scripts/send-pending-alerts.sh`.
- Output: "✓ Sent: INFO - Test Deploy" for admin server.
- (Direct curl attempts from servers often fail/empty due to provider blocks, as expected; spool path used successfully. User should see the test in -1003795574407 now.)
- Pending cleared after send.

## What remains (for architect / code changes)
- The `backup_run` UPDATE bug in the script inside `infra/Dockerfile.db-backup` (psql | tr mangling ID). Dumps work, accounting/heartbeat/replication status do not.
- Committed `infra/docker-compose.prod.yml` (and no-domain) lack `ports:` for db/redis (despite pinbetting.txt claiming they were added for dedicated worker). Dev-only in override.
- bot-only compose on worker deployment is stale vs v0.2.0 replication volume/env patterns in prod.yml.
- No automatic key/dir chown or entrypoint fix in image for bb user + mounted secret (relies on host chown 999).
- Heartbeat delivery relies on spool from control (direct often blocked).
- Suggest: architect prepares urgent code fixes (fix script ID capture with -q -t -A | head -1; add ports: to prod compose with comments/firewall note; improve bot image for key handling or docs for chown; perhaps make bot-only example in repo or update deployment docs).
- After code fixes, redeploy (rebuild images, use new compose commands).

## Verification commands used (for reproducibility)
- Queries on backup_run, ls volumes, docker logs db-backup (showed the UPDATE error).
- ls on Bot /opt/backups, docker logs bot (replication registration only).
- Inside exec: id, ls -l key, python os.access, TCP socket connect tests (pre/post ports: failed -> OK).
- iptables, docker port, compose ps, build_info inside containers (confirmed v0.2.0 commit).
- Pending creation + /home/nm/scripts/send-pending-alerts.sh run (✓ Sent).

## Next steps for user
- Confirm receipt of the test message in the admin channel.
- Ask architect to review this report (and the handoff file) and prepare sprints for the code-level fixes listed.
- For ongoing: include `/tmp/db-ports-override.yml` (or equivalent) in Admin compose commands; keep the host chowns (perhaps add to apply-bot-firewall.sh or a deploy bootstrap).
- Re-check in 1h: expect success rows in backup_run (once script fixed), replicated files on Bot, heartbeat messages in channel.

**Deployment errors (ports, perms, spool delivery) eliminated via ops only. Code issues handed off.**

---

This file created per user request as handoff transmission. No project source (src/, committed ymls, Dockerfiles) modified. All server changes were runtime/deployment (chown, /tmp override, spools, restarts, script runs).