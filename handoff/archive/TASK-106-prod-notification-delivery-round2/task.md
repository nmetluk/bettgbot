---
id: TASK-106
created: 2026-06-03
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - handoff/outbox/TASK-105-report.md
  - handoff/outbox/backup-replication-deployment-audit-2026-06-03.md
priority: high
estimate: S
---

# TASK-106: Раунд-2 на проде — починить доставку уведомлений (токен/канал/инстанс) + перепроверка

## Контекст

TASK-105 показал (отчёт `handoff/outbox/TASK-105-report.md`):
- **Критфикс `backup_run` работает** (id 14 → `success`).
- **Egress НЕ заблокирован на воркере**: с контейнера бота на воркере (195.133.26.200) `container->telegram: 200`. А вот реальный `sendMessage` вернул **`404 Not Found`** → это признак **неверного токена бота** (а не «бот не в канале» — тогда был бы 400/403).
- **На Admin (5.188.88.78) сети до Telegram нет вообще** (`Network is unreachable`), но там тоже крутится `bettgbot-bot-1` → **это ОШИБКА деплоя** (подтверждено владельцем): бот должен работать **только на воркере**. Admin-бот шлёт в никуда, плодит ошибки и дублирует scheduler-работу.
- Heartbeat в 20:07 упал на `ConnectionRefused` к БД (порты применили позже) — должен отработать на 21:07.
- Репликация пока без файлов (до фикса не было `success`-строки).

Вывод проектировщика: **spool НЕ нужен** — прямая доставка с воркера заработает после починки токена + слать только с воркера. Эта задача — ops-раунд на проде: подтвердить/починить токен, убедиться в членстве бота в канале, гейтить уведомления на воркер, перепроверить heartbeat и репликацию. **Без правок кода/репо** (кроме отчёта). Серверные `.env`/рестарты — допустимы.

> 🔒 Маскировать в отчёте: токен, пароли, ключ, телефоны.

## Что сделать (на серверах) и записать сырые выводы в `handoff/outbox/TASK-106-report.md`

### 1. Валидность токена бота [BOT — воркер]
```bash
TOKEN=$(docker exec "$(docker ps -qf name=bettgbot-bot)" printenv TELEGRAM_BOT_TOKEN)
curl -sS -m 10 "https://api.telegram.org/bot${TOKEN}/getMe"
```
- `{"ok":true,"result":{"username":...}}` → токен валиден, перейти к п.2.
- `{"ok":false,"error_code":404}` → **токен неверный**: поправить `TELEGRAM_BOT_TOKEN` в `.env` воркера (взять актуальный у владельца/из BotFather), `docker compose ... up -d bot`, повторить `getMe`. В отчёт — факт «токен был неверный/верный» (без самого токена).

### 2. Членство бота в канале + реальная отправка [BOT]
```bash
curl -sS -m 10 "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id=-1003795574407 --data-urlencode "text=TASK-106 round2 direct from worker $(date -u)"
```
- `ok:true` → доставка напрямую работает ✓ (проверь, что сообщение реально в канале).
- `400 chat not found` / `403 ... not a member` → **добавить бота в канал `-1003795574407` как админа** (вручную через Telegram), повторить.

### 3. Убрать бот с Admin (ошибка деплоя) + уведомления на воркере [ADMIN + BOT]
Бот на Admin — ошибка; он должен быть **только на воркере**.
- На **Admin**: остановить и не поднимать бот. Сейчас он стартует из `prod.yml` (профиль с сервисом `bot`). Временно: `docker compose ... stop bot && docker compose ... rm -f bot` (или поднимать Admin без профиля бота). Убедиться, что `docker ps` на Admin **не содержит** `bettgbot-bot-1`, и он не вернётся после рестарта/перезагрузки (проверить `restart:` и профиль).
  > Постоянный фикс в репо (Admin-compose не должен поднимать `bot`) — оформит проектировщик отдельной задачей; здесь только снять на сервере.
- На **Воркере**: `BACKUP_HEARTBEAT_ENABLED=true` + `ADMIN_TELEGRAM_CHAT_IDS=-1003795574407` + `BACKUP_REPLICATION_ENABLED=true`. Рестарт. В отчёт — имена флагов + `<set>` (без значений).

### 4. Подтвердить топологию [ADMIN + BOT]
- В отчёт: `docker ps` на Admin (бот отсутствует) и на воркере (бот один, healthy).
- На воркере зафиксировать, какие scheduler-джобы реально крутятся (один источник истины):
```bash
docker logs "$(docker ps -qf name=bettgbot-bot)" --since 30m 2>&1 | grep -iE "Running job|dispatch_reminders|dispatch_broadcasts|heartbeat|event_result|replicate" | tail -30
```

### 5. Перепроверка после :07 [BOT]
Дождаться ближайшей `:07`, затем:
```bash
docker logs "$(docker ps -qf name=bettgbot-bot)" --since 15m 2>&1 | grep -iE "heartbeat|send|telegram|error|timeout|forbidden" | tail -30
```
- В отчёт: **пришёл ли heartbeat в канал** и что в логах (успех vs ошибка).

### 6. Репликация после нового success [BOT]
```bash
docker exec "$(docker ps -qf name=bettgbot-bot)" sh -c 'ls -lt /backups 2>/dev/null | head'
docker logs "$(docker ps -qf name=bettgbot-bot)" --since 30m 2>&1 | grep -iE "replicat|rsync|ssh|permission" | tail -20
# и статус в БД:
docker exec "$(docker ps -qf name=bettgbot-db)" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c \
"SELECT id,status,filename,replicated_at FROM backup_run WHERE status='success' ORDER BY id DESC LIMIT 5;" 2>/dev/null
```
- В отчёт: появились ли файлы на воркере и проставлен ли `replicated_at` у свежего success (id 14+).

## Definition of Done
- [ ] Отчёт `handoff/outbox/TASK-106-report.md` с выводами п.1–6 (секреты замаскированы).
- [ ] Явные ответы: токен валиден? sendMessage с воркера = ok? heartbeat реально пришёл в канал? репликация проставила `replicated_at`?
- [ ] **Бот снят с Admin** (в `docker ps` на Admin его нет и не возвращается); бот работает только на воркере.
- [ ] Ops-only, репо/код не менять. Move inbox→archive, отчёт коммитнуть, PR/auto-merge.

## Ссылки
- Предыдущий раунд: [`handoff/outbox/TASK-105-report.md`](../outbox/TASK-105-report.md)
- Инфра-фиксы (отдельно, не на проде): TASK-103 (порты), TASK-104 (воркер-compose/права)
