#!/bin/bash
# apply-bot-firewall.sh
#
# Idempotent setup of DOCKER-USER iptables rules to expose Postgres (5432) and
# Redis (6379) ONLY to the dedicated worker bot IP.
#
# This is the enforcement half of TASK-103 ports-permanent (amendment).
# The "expose" is done by the opt-in overlay infra/docker-compose.expose-db.yml .
# Without this script the ports would be open to the world (CRITICAL regression).
#
# REQUIREMENTS / USAGE (run on Admin host, as root or via sudo):
#   WORKER_IP=195.133.26.200 sudo scripts/apply-bot-firewall.sh
#
#   # Re-run is safe (idempotent). Run after every reboot or docker restart if rules lost.
#
#   # To make persistent on Ubuntu:
#   #   - copy script to /usr/local/sbin/apply-bot-firewall.sh
#   #   - add to /etc/rc.local or create systemd oneshot service, or use iptables-persistent
#   #     (but re-apply after docker daemon restart is recommended because DOCKER-USER is managed by docker).
#
# ENV:
#   WORKER_IP   (required) — IPv4 of the worker bot host (the only IP allowed to reach 5432/6379)
#
# BEHAVIOR:
#   - Inserts at the top of DOCKER-USER chain (before Docker's own rules):
#       ACCEPT tcp dport 5432 from $WORKER_IP
#       DROP   tcp dport 5432 (everything else)
#       same for 6379
#   - Existing rules for these dports are removed first (idempotent).
#   - Only IPv4 (iptables). For IPv6 add ip6tables equivalent if your setup uses it.
#   - Does NOT touch INPUT/FORWARD etc. — only DOCKER-USER (the hook Docker provides for this).
#
# VERIFICATION after run:
#   sudo iptables -L DOCKER-USER -n -v | grep -E '5432|6379'
#   # Should show the two ACCEPT (worker) followed by DROP lines near top.
#
# See also:
#   infra/docker-compose.expose-db.yml
#   docs/07-deployment.md (split topology + firewall step)
#   handoff/outbox/TASK-103-amendment-report.md
#   TASK-047 (no-domain must stay closed), TASK-100 (replication needs the access)
#
# DO NOT RUN on single-host or no-domain without the overlay + worker separation.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must run as root (or with sudo)." >&2
  exit 1
fi

WORKER_IP="${WORKER_IP:-}"
if [[ -z "$WORKER_IP" ]]; then
  echo "ERROR: WORKER_IP env var is required (e.g. WORKER_IP=1.2.3.4 $0)" >&2
  echo "       This is the IP of your dedicated worker bot host." >&2
  exit 1
fi

# Validate rough IPv4 (not perfect but good enough)
if ! [[ "$WORKER_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: WORKER_IP='$WORKER_IP' does not look like IPv4 address." >&2
  exit 1
fi

echo "==> Applying DOCKER-USER whitelist for worker $WORKER_IP (ports 5432, 6379)"
echo "    (idempotent: old rules for these dports will be removed first)"

# Helper: remove any existing rules that match the pattern (by recreating the chain rules we care about)
# We delete by content using -D in a loop until gone.
remove_rules_for_port() {
  local port=$1
  # Delete all occurrences of rules we may have inserted previously (ACCEPT from worker + DROP for the port)
  while iptables -C DOCKER-USER -p tcp --dport "$port" -s "$WORKER_IP" -j ACCEPT 2>/dev/null; do
    iptables -D DOCKER-USER -p tcp --dport "$port" -s "$WORKER_IP" -j ACCEPT || true
  done
  while iptables -C DOCKER-USER -p tcp --dport "$port" -j DROP 2>/dev/null; do
    iptables -D DOCKER-USER -p tcp --dport "$port" -j DROP || true
  done
}

remove_rules_for_port 5432
remove_rules_for_port 6379

# Now insert at position 1 (top). Insert order matters: we want ACCEPT specific first, then DROP.
# Because each -I 1 pushes previous to 2 etc., we insert the DROP first, then the ACCEPT (so ACCEPT ends up before DROP).
# Safer: insert DROP at 1, then ACCEPT at 1 (ACCEPT becomes 1, DROP becomes 2).

# For 5432
iptables -I DOCKER-USER 1 -p tcp --dport 5432 -j DROP
iptables -I DOCKER-USER 1 -p tcp --dport 5432 -s "$WORKER_IP" -j ACCEPT

# For 6379
iptables -I DOCKER-USER 1 -p tcp --dport 6379 -j DROP
iptables -I DOCKER-USER 1 -p tcp --dport 6379 -s "$WORKER_IP" -j ACCEPT

echo "==> Rules applied. Current relevant DOCKER-USER fragment:"
iptables -L DOCKER-USER -n -v --line-numbers | head -20

echo ""
echo "==> Done. Re-run any time (safe). Make persistent via rc.local / systemd / cron @reboot if desired."
echo "    Example one-liner for rc.local (after making script +x and owned by root):"
echo "      WORKER_IP=1.2.3.4 /path/to/apply-bot-firewall.sh || true"
echo ""
echo "    Test from worker: psql -h <ADMIN_IP> -p 5432 ... should succeed; from other IP should be refused (or timeout on DROP)."
