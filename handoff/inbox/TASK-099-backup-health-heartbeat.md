---
id: TASK-099
created: 2026-06-01
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/operational-backup-heartbeat-proposal.md
  - docs/03-data-model.md
  - docs/04-bot-flows.md
  - docs/07-deployment.md
priority: high
estimate: M
---

# TASK-099: Backup health heartbeat внутри бота (через таблицу `backup_run`)

## Контекст

При диагностике прода (2026-06-01) исполнитель обнаружил, что бэкап-схема из `pinbetting.txt` фактически **не работает**: на Admin-сервере есть cron `/etc/cron.d/bettgbot-backup` (ежечасно `backup-db.sh --with-redis`), но скриптов (`backup-db.sh`, `check-bot-db-visibility.sh`, `notify-telegram.sh`) на серверах нет → крон каждый час падает «No such file», свежих бэкапов по этой схеме нет, алерты не доставляются. Полный разбор — [`handoff/outbox/operational-backup-heartbeat-proposal.md`](../outbox/operational-backup-heartbeat-proposal.md).

Решение владельца: внешнюю cron-схему выпиливаем, мониторинг бэкапов и видимости БД переносим внутрь бота (паттерн TASK-097). Физический `pg_dump`/ротацию оставляет контейнер `db-backup` (TASK-029). **Источник правды о бэкапах — таблица `backup_run` в Postgres** (а не файлы в volume): это снимает проблему топологии — бот читает статус из БД с любого хоста, без монтирования backup-volume и co-location.

> ⚠️ **Срочный ops-пункт (вне этой задачи, owner-direct):** убрать битый `/etc/cron.d/bettgbot-backup` с серверов и подтвердить, что контейнер `db-backup` реально пишет дампы. Это не код-задача — делает владелец на сервере.

## Цель

1. Таблица `backup_run` — каждый запуск бэкапа пишет туда строку (start → success/failed + размер).
2. Ежечасный bot-джоб `send_backup_health_heartbeat`: читает последнюю строку `backup_run` + проверяет видимость Postgres/Redis из инстанса бота, шлёт статус в `ADMIN_TELEGRAM_CHAT_IDS`, алертит при просрочке/ошибке/отсутствии бэкапа.

## Архитектура (ответы на вопросы proposal + решение по backup_run)

- **Источник свежести:** таблица `backup_run` (НЕ файлы в volume). Продюсер дампов (контейнер `db-backup`) после `pg_dump` пишет строку через `psql`. Бот читает последнюю строку. Топология серверов больше не важна — volume монтировать не нужно.
- **Частота/флаг:** `CronTrigger(minute=7)` (ежечасно). Флаг `BACKUP_HEARTBEAT_ENABLED` (env, default `false`); при `false` джоб не регистрируется. Флаг заменяет primary-guard — включаем на **одном** инстансе бота, чтобы не было дублей (любой подойдёт, т.к. читает БД).
- **Порог алерта:** `BACKUP_MAX_AGE_HOURS` (env, default `2`). Алерт если: нет ни одной `success`-строки; последняя успешная старше порога; последняя строка `failed`; Postgres/Redis недоступны.
- **db-backup контейнер:** остаётся продюсером дампов + ротация. Добавляется только запись в `backup_run`.
- **Тексты:** константы `OPERATIONAL_HEARTBEAT_*` в `src/bot/texts.py`.

## Модель `backup_run` (миграция 0008)

Поля: `id` PK; `started_at` timestamptz NOT NULL; `finished_at` timestamptz NULL; `status` text NOT NULL (`running|success|failed`); `size_bytes` bigint NULL; `host` text NULL (какой сервер произвёл — на будущее для multi-server); `error` text NULL; `created_at` timestamptz default now(). Индекс по `finished_at DESC` (быстрый «последний успешный»). Реплика-статус/детали — backlog, не сейчас.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-099-report.md`.

- [ ] Миграция **0008** `backup_run` (up/down). Модель `BackupRun` в `src/shared/models/`. Apply+rollback чисто.
- [ ] `BackupRunRepository`: `get_last_success()` / `get_latest()` (read). Запись делает не Python, а скрипт контейнера — но добавить тонкий хелпер/SQL-док для воспроизводимости.
- [ ] **Контейнер `db-backup`** (`infra/Dockerfile.db-backup` / inline-скрипт в prod-compose): обернуть `pg_dump` — перед началом `INSERT ... status='running'`, после успеха `UPDATE ... status='success', finished_at, size_bytes=<размер gz>`, при ошибке `status='failed', error`. Запись через `psql` к тому же `db`. Не ломать существующую ротацию.
- [ ] `Settings`: `backup_heartbeat_enabled: bool` (`BACKUP_HEARTBEAT_ENABLED`, default `false`), `backup_max_age_hours: int` (`BACKUP_MAX_AGE_HOURS`, default `2`).
- [ ] Хелпер проверок видимости: `SELECT 1` через app `engine` (с таймаутом) + Redis `ping` (если Redis сконфигурирован).
- [ ] Джоб `send_backup_health_heartbeat(*, bot, session_maker)` в `jobs.py`: читает `backup_run`, собирает статус (возраст последнего success, размер, статус последней строки) + видимость БД/Redis, форматирует (тексты `OPERATIONAL_HEARTBEAT_*`), шлёт во все `ADMIN_TELEGRAM_CHAT_IDS`. Пустой список → `warning` + return. Ошибка отправки в один чат → `warning`, продолжаем.
- [ ] Регистрация в `builder.py` **только если** `backup_heartbeat_enabled`: `CronTrigger(minute=7)`, `id="send_backup_health_heartbeat"`, `coalesce=True`, `max_instances=1`, `misfire_grace_time` ~600.
- [ ] Compose: env `BACKUP_HEARTBEAT_ENABLED`, `BACKUP_MAX_AGE_HOURS` в сервис `bot` + `.env.*example` (default выключено). **Volume backup в бот монтировать НЕ нужно** (читаем из БД).
- [ ] Тесты с замоканным `Bot` и фикстурами `backup_run`: свежий `success` → «ОК»; последний success старше порога → алерт; последняя строка `failed` → алерт; строк нет → алерт; БД/Redis недоступны → алерт; пустой `ADMIN_TELEGRAM_CHAT_IDS` → не шлёт; `backup_heartbeat_enabled=false` → джоб НЕ зарегистрирован (`test_builder`). integration на `BackupRunRepository.get_last_success`.
- [ ] `ruff` / `mypy src/shared` / `pytest` зелёные.
- [ ] PR `TASK-099: backup health heartbeat`; отчёт в outbox; move inbox→archive; **ветка отребейзена на свежий `main` перед PR** (иначе auto-merge не встанет — урок TASK-097).

## Артефакты

```
+ src/migrations/versions/0008_backup_run.py
+ src/shared/models/backup_run.py            # модель BackupRun
* src/shared/models/__init__.py              # экспорт
+ src/shared/repositories/backup_run.py      # get_last_success / get_latest
* src/shared/config.py                       # 2 новых поля
+ src/bot/_backup_health.py (или в jobs)     # ping Postgres/Redis + сборка статуса
* src/bot/scheduler/jobs.py                  # send_backup_health_heartbeat
* src/bot/scheduler/builder.py               # условная регистрация
* src/bot/texts.py                           # OPERATIONAL_HEARTBEAT_*
* infra/Dockerfile.db-backup / docker-compose.prod*.yml  # запись backup_run в скрипте
* infra/.env.*example
+ tests/...
```

## Ссылки

- Proposal: [`handoff/outbox/operational-backup-heartbeat-proposal.md`](../outbox/operational-backup-heartbeat-proposal.md)
- Паттерн джобов/отправки: TASK-097 (`send_daily_admin_digest`, `dispatch_event_result_notifications`)
- Бэкап-контейнер: `infra/docker-compose.prod*.yml`, `infra/Dockerfile.db-backup` (`db-backup`, TASK-029)
- Решение: [`state/DECISIONS.md`](../../state/DECISIONS.md) (2026-06-01)

## Не делать в этой задаче (backlog)

- Репликация дампов на второй сервер и её статус в `backup_run` (поле под это добавим позже).
- pending-alerts-файл как fallback при egress-проблемах.
- Перенос самого `pg_dump`/ротации в бот — остаётся в `db-backup`.
- `docs/`/`state/` не трогать — обновит cowork.
