---
task: TASK-103
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/XXX
branch: feature/TASK-103-ports-permanent
commits:
  - chore(infra): add permanent ports 5432/6379 for db/redis in prod compose (TASK-103)
---
# Отчёт по TASK-103: Постоянные порты для DB/Redis (worker connectivity, ports в prod.yml)

## Сводка

Выполнен infra-фикс "TASK-103 (порты)" referenced в TASK-106/task.md и детально описанный в аудитах TASK-105.

- Добавлены `ports:` для `db` (5432) и `redis` (6379) в `infra/docker-compose.prod.yml` и `prod-no-domain.yml`.
- Добавлены подробные комментарии с отсылками к аудитам (handoff/archive/TASK-105-report.md), firewall DOCKER-USER, и будущему docs/07-deployment.md.
- Это заменяет временный /tmp override, использованный в прод-диагностике (TASK-105/106).
- db/redis services всегда публикуются (не под профилем bot из TASK-107), чтобы worker мог подключаться независимо от того, поднят ли bot на Admin.
- Для no-domain (single-host bootstrap) — тоже, с учётом что later может быть split.
- Проверка: `docker compose -f ...prod.yml config` показывает ports под db/redis; admin-набор (без --profile bot) корректно включает db/redis с портами, исключает bot.

Не затронуто: src/, тесты (инфра), volumes, depends_on, healthchecks.

## Изменённые файлы

```
* infra/docker-compose.prod.yml            # + ports + комментарий TASK-103 для db и redis
* infra/docker-compose.prod-no-domain.yml  # + ports + комментарий (с учётом single-host)
```

## Как воспроизвести / запустить

```bash
# Admin/prod compose (db/redis должны иметь порты, bot — нет)
POSTGRES_USER=... POSTGRES_PASSWORD=... POSTGRES_DB=... TELEGRAM_BOT_TOKEN=... \
  ADMIN_SECRET_KEY=... ADMIN_CSRF_SECRET=... ADMIN_DOMAIN=... \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config --services
# Ожидание: db, redis, web, nginx, db-backup, certbot (bot отсутствует благодаря TASK-107)

# Проверить порты
... config | grep -A5 '  db:' | grep -A2 ports
# ports: - "5432:5432"

# То же для no-domain
... -f infra/docker-compose.prod-no-domain.yml config | grep -E '5432|6379'

# Применить на прод (как в аудитах, но теперь без /tmp)
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d db redis
docker port <db-container> 5432   # должно показать 0.0.0.0:5432
```

После деплоя — применить firewall (iptables в DOCKER-USER для 195.133.26.200 → 5432/6379 на Admin 5.188.88.78).

## Что не сделано (если применимо)

- Не обновлял `docs/07-deployment.md` — по аналогии с предыдущими infra-задачами (107 и т.п.) текст даётся здесь в отчёте (cowork впишет).
- Не создавал/не правил task.md в inbox (TASK-103 не был опубликован в `handoff/inbox/` на момент взятия; только упоминание в TASK-106 archive + детали в TASK-105 report. Реконструировал по контексту; при необходимости cowork опубликует формальный task.md).
- Не добавлял ports в base compose (dev использует override.yml с 127.0.0.1 — оставлено).
- Не правил .env.example или другие (порты — compose concern).
- Полный pytest имеет 2 pre-existing фейла (date-dependent в analytics, TASK-102 scope) — не связаны с инфра.

## Открытые вопросы для проектировщика

- Точный текст для вставки в `docs/07-deployment.md` (секция про cross-server access / firewall для worker). Предлагаю ниже.
- Нужно ли для no-domain публиковать на 127.0.0.1:5432 (как nginx) или на 0.0.0.0 (как сделал)? Сейчас 0.0.0.0 для consistency с worker-connectivity.
- Firewall правила — документировать пример iptables / ufw / systemd для DOCKER-USER? (в TASK-105 предлагали).
- В будущем (TASK-108 replication paths) — ports + bind-mounts вместе в одном PR или отдельно?
- Если single-host no-domain всегда будет только на Admin (без отдельного worker), можно ли conditional ports? (сложно в compose без profiles на db/redis).

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-103: постоянные порты 5432/6379 для db/redis в prod*.yml (worker connectivity, замена /tmp override из аудитов TASK-105/106). Комментарии про firewall DOCKER-USER. (PR #XXX)

## Текст для docs/07-deployment.md (предлагаемый для вставки cowork'ом)

(Вставить в раздел про прод-деплой, после описания compose, перед или после firewall для nginx, в секцию "Cross-server access (Admin ↔ Worker)")

### DB / Redis ports для worker

На Admin-сервере (5.188.88.78) db и redis публикуются в `infra/docker-compose.prod.yml` (и no-domain):

```yaml
  db:
    ports:
      - "5432:5432"
  redis:
    ports:
      - "6379:6379"
```

**ВАЖНО:** это экспонирует порты на 0.0.0.0. Обязательно настрой firewall (DOCKER-USER chain в iptables Docker'а), чтобы только IP воркера (195.133.26.200) мог подключаться:

Пример (применять после каждого ребута или через скрипт в /etc/rc.local / systemd):

```bash
# На Admin
iptables -I DOCKER-USER -i ext_if -p tcp -s 195.133.26.200 --dport 5432 -j ACCEPT
iptables -I DOCKER-USER -i ext_if -p tcp -s 195.133.26.200 --dport 6379 -j ACCEPT
# drop по умолчанию для других (или existing rules)
```

См. также аудит TASK-105 (handoff/archive/TASK-105-...) где временно использовали /tmp override + apply правил.

На воркере bot в .env использует `DATABASE_URL` / `REDIS_URL` с хостом Admin (ADMIN_DOMAIN или IP).

Для no-domain (bootstrap) — те же порты (single-host или будущий split).

## Метрики (опционально)

- Тестов: 0 (инфра)
- Время: ~30 мин (анализ контекста из 105/106, edits, verify compose)
