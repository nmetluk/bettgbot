---
id: TASK-105
created: 2026-06-03
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - handoff/outbox/backup-replication-deployment-audit-2026-06-03.md
priority: high
estimate: S
---

# TASK-105: Прод-диагностика бэкапов, репликации и доставки уведомлений (только чтение/тесты)

## Контекст

После v0.2.0 и деплой-аудита (PR #214) нужно **проверить на живых серверах**, что заработало, а что нет — особенно открытый вопрос: **доходят ли уведомления бота в Telegram напрямую** (провайдер часто блокирует egress с VPS) и **чинится ли `backup_run`** после критфикса `start_backup_run` (`-tAq | head -1`).

Это **ops-диагностика, без правок кода**. Задача исполнителя — прогнать команды ниже на серверах и сложить **сырые выводы** в отчёт. По ним проектировщик примет решения (нужен ли spool-механизм, всё ли с репликацией).

Серверы: **Admin** `5.188.88.78` (db, redis, db-backup, web) и **Worker/Bot** `195.133.26.200` (bot). Где запускать — помечено [ADMIN]/[BOT].

> ⚠️ Перед прогоном секций B/F убедись, что критфикс №1 (`fix(backup): capture backup_run id`) **влит и db-backup-образ пересобран+перезапущен** на Admin (`docker compose ... up -d --build db-backup`). Иначе `backup_run` останется 'running'. Если ещё не пересобрано — отметь это в отчёте и прогони, что можешь.

## Что сделать

Прогнать секции A–G, **записать вывод каждой команды дословно** в `handoff/outbox/TASK-105-report.md` (под соответствующими заголовками). Где нужно — короткий комментарий «ожидалось / получили».

### 🔒 Редактирование секретов (обязательно)
- **НЕ** вставлять в отчёт: токен бота, пароли БД, содержимое `.env` целиком, приватный SSH-ключ, телефоны пользователей. Токен в командах подставлять из переменной, в отчёт — маскировать (`bot<redacted>`).

### A. Версии/состояние [ADMIN]+[BOT]
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
# build_info внутри бота (подтвердить v0.2.0):
docker exec "$(docker ps -qf name=bot)" python -c "from src.shared.build_info import get_build_info as g;print(g())" 2>&1 | head
# какие BACKUP_*/ADMIN_TELEGRAM флаги выставлены (только ИМЕНА и факт непустоты, не значения):
docker exec "$(docker ps -qf name=bot)" sh -c 'env | grep -E "BACKUP_|ADMIN_TELEGRAM|REPLICATION" | sed "s/=.*/=<set>/"' 2>&1
```

### B. Дампы и backup_run [ADMIN]
```bash
# последние строки backup_run — статусы, finished_at, filename, size, replicated_at:
docker exec "$(docker ps -qf name=db)" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c \
"SELECT id,status,started_at,finished_at,size_bytes,filename,replicated_at,host FROM backup_run ORDER BY id DESC LIMIT 10;"
# файлы дампов в volume:
docker exec "$(docker ps -qf name=db-backup)" sh -c 'ls -lt /backups | head'
# свежие логи db-backup (ищем ошибки UPDATE / 'trailing junk'):
docker logs "$(docker ps -qf name=db-backup)" --since 2h 2>&1 | tail -40
```
Ожидание после критфикса: новые строки доходят до `status=success` с `finished_at`/`filename`/`size_bytes`.

### C. Egress в Telegram [BOT] (и для сравнения [ADMIN])
```bash
# сырая достижимость с хоста и изнутри контейнера бота:
curl -sS -m 10 -o /dev/null -w "host->telegram: %{http_code}\n" https://api.telegram.org
docker exec "$(docker ps -qf name=bot)" sh -c \
 'curl -sS -m 10 -o /dev/null -w "container->telegram: %{http_code}\n" https://api.telegram.org 2>/dev/null \
  || python -c "import urllib.request as u;print(\"container->\",u.urlopen(\"https://api.telegram.org\",timeout=10).status)"'

# реальная отправка ботом в канал (ТОКЕН в переменную, в отчёт — маскировать):
TOKEN='<BOT_TOKEN>'
curl -sS -m 15 "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id=-1003795574407 --data-urlencode "text=TASK-105 egress test from $(hostname) $(date -u)"
```
В отчёт: коды HTTP и `{"ok":...}` (без токена). Пришло ли сообщение в канал — отметить.

### D. Живой heartbeat/доставка [BOT]
```bash
# дождаться ближайшей минуты :07 (cron heartbeat) ИЛИ отметить время прогона; затем:
docker logs "$(docker ps -qf name=bot)" --since 20m 2>&1 | grep -iE "heartbeat|backup|admin_digest|telegram|send|error|timeout|forbidden" | tail -40
```
В отчёт: пришло ли сообщение heartbeat в канал; что в логах — успех vs `TelegramNetworkError`/timeout/Forbidden.

### E. Доступ к БД/Redis с воркера [BOT]
```bash
docker exec "$(docker ps -qf name=bot)" python - <<'PY' 2>&1
import socket
for host,port in [("5.188.88.78",5432),("5.188.88.78",6379)]:
    s=socket.socket(); s.settimeout(6)
    try: s.connect((host,port)); print(host,port,"OK")
    except Exception as e: print(host,port,"FAIL",e)
    finally: s.close()
PY
# и ошибки коннекта к БД в логах бота:
docker logs "$(docker ps -qf name=bot)" --since 30m 2>&1 | grep -iE "connection refused|operationalerror|could not connect|redis" | tail -20
```

### F. Репликация [BOT]
```bash
# появились ли реплицированные дампы локально на воркере:
ls -lt /opt/backups/bettgbot/db/ 2>/dev/null | head   # путь уточни по BACKUP_LOCAL_DIR
docker exec "$(docker ps -qf name=bot)" sh -c 'ls -lt /backups 2>/dev/null | head'
# логи джоба репликации:
docker logs "$(docker ps -qf name=bot)" --since 30m 2>&1 | grep -iE "replicat|rsync|ssh|permission|key" | tail -30
```
(Связано с B: репликация берёт последний `success` из backup_run — без критфикса ей нечего тянуть.)

### G. Свободная диагностика
Если что-то выглядит сломанным — копай дальше и приложи в отчёт: любые относящиеся логи/ошибки, `docker inspect`, права на ключ (`ls -l` примонтированного ключа + `id` внутри контейнера), `iptables -L -n` фрагмент по 5432/6379, и т.п. Проектировщик явно просил: **прогоняй любые тесты, которые помогут понять картину.**

## Definition of Done
- [ ] Отчёт `handoff/outbox/TASK-105-report.md` с сырыми выводами секций A–G и краткими пометками «ожидалось/получили». Секреты замаскированы.
- [ ] Явный вывод по двум вопросам: (1) `backup_run` доходит до `success`? (2) прямой egress бота в Telegram работает (да/нет, по пунктам C/D)?
- [ ] Это диагностика — кода/инфры не менять. Move inbox→archive, отчёт коммитнуть, PR/auto-merge как обычно.

## Ссылки
- Аудит-предшественник: [`handoff/outbox/backup-replication-deployment-audit-2026-06-03.md`](../outbox/backup-replication-deployment-audit-2026-06-03.md)
- Критфикс id: коммит `fix(backup): capture backup_run id` (PR `chore/handoff-fix-backup-run-id`)
