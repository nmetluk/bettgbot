---
id: TASK-109
created: 2026-06-03
author: cowork-agent
parallel-safe: true
blockedBy: [TASK-104, TASK-107, TASK-108]
related:
  - handoff/outbox/TASK-106-report.md
priority: normal
estimate: S
---

# TASK-109: Финальное АВТО-подтверждение на проде (heartbeat + репликация, без ручных действий)

## Контекст

TASK-106 доказал прямую доставку в канал и снял бот с Admin, но **два момента не наблюдались в автоматике**: реальный heartbeat в `:07` и срабатывание джоба `replicate_latest_backup` (репликацию делали руками для демонстрации). Эта задача — прогнать на проде **после вливания TASK-104/107/108 и пересборки/редеплоя контейнеров** и убедиться, что всё работает **само, без ручных rsync/UPDATE/симлинков**.

## Предусловие (проверить перед прогоном)
- TASK-107 влит и задеплоен: бот **только на воркере** (на Admin в `docker ps` бота нет, не возвращается после рестарта).
- TASK-104 + TASK-108 влиты и задеплоены: воркерный bot-only compose с `BACKUP_LOCAL_DIR=/backups`, Admin db-backup пишет дампы в **хостовый bind-mount** (источник ssh-репликации), без ручного симлинка.
- Образы пересобраны (`--build`), контейнеры подняты новыми compose/.env. Если что-то из этого ещё не задеплоено — отметить в отчёте и прогнать, что можно.

> 🔒 Маскировать секреты (токен/пароли/ключ/телефоны).

## Что подтвердить (записать сырые выводы в `handoff/outbox/TASK-109-report.md`)

### 1. Heartbeat сам дошёл в канал [BOT]
Дождаться ближайшей `:07` UTC (НЕ слать вручную). Затем:
```bash
docker logs "$(docker ps -qf name=bettgbot-bot)" --since 15m 2>&1 | grep -iE "heartbeat|backup_health|sent|skipped|telegram|error" | tail -20
```
- В отчёт: появилась ли строка отправки (`scheduler.backup_heartbeat.sent`/успех) **и реально ли пришло сообщение в канал `-1003795574407`** (проверить глазами/историю канала). Текст (OK/ALERT).

### 2. Репликация сама отработала [BOT]
Без ручного rsync/UPDATE. Дождаться нового часового `success` (раздел B) и тика `replicate_latest_backup` (15m):
```bash
# свежий success в БД:
docker exec "$(docker ps -qf name=bettgbot-db)" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c \
"SELECT id,status,filename,finished_at,replicated_at FROM backup_run WHERE status='success' ORDER BY id DESC LIMIT 3;"
# файлы, появившиеся на воркере САМИ:
docker exec "$(docker ps -qf name=bettgbot-bot)" sh -c 'ls -lt /backups/*.sql.gz 2>/dev/null | head'
# логи джоба:
docker logs "$(docker ps -qf name=bettgbot-bot)" --since 30m 2>&1 | grep -iE "replicate|rsync|mark_replicated|permission|error" | tail -20
```
- В отчёт: появился ли **новый** (не id 14) дамп на воркере и проставлен ли его `replicated_at` **автоматически** (джобом, без ручных действий).

### 3. Топология стабильна после редеплоя
```bash
# на Admin:
docker ps --format '{{.Names}}' | grep -c bettgbot-bot   # ожидание: 0
# на воркере:
docker ps --format '{{.Names}}' | grep bettgbot-bot       # ровно один
```

## Definition of Done
- [ ] Отчёт `handoff/outbox/TASK-109-report.md` с сырыми выводами п.1–3 (секреты замаскированы).
- [ ] Явные ответы: (1) heartbeat **сам** пришёл в канал? (2) репликация **сама** скопировала новый дамп и проставила `replicated_at`? (3) бот только на воркере и после редеплоя?
- [ ] Ops-only, без ручных rsync/UPDATE/симлинков (в этом весь смысл). Move inbox→archive, отчёт, PR/auto-merge.

## Ссылки
- Раунд-2: [`handoff/outbox/TASK-106-report.md`](../outbox/TASK-106-report.md)
- Пути репликации: TASK-108; воркер-compose: TASK-104; бот-на-воркере: TASK-107
