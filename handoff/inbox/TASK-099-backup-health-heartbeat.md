---
id: TASK-099
created: 2026-06-01
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/operational-backup-heartbeat-proposal.md
  - docs/04-bot-flows.md
  - docs/07-deployment.md
priority: high
estimate: M
---

# TASK-099: Backup health heartbeat внутри бота

## Контекст

При диагностике прода (2026-06-01) исполнитель обнаружил, что бэкап-схема из `pinbetting.txt` фактически **не работает**: на Admin-сервере есть cron `/etc/cron.d/bettgbot-backup` (ежечасно `backup-db.sh --with-redis`), но скриптов (`backup-db.sh`, `check-bot-db-visibility.sh`, `notify-telegram.sh`) на серверах нет → крон каждый час падает «No such file», свежих бэкапов по этой схеме нет, алерты не доставляются. Полный разбор — [`handoff/outbox/operational-backup-heartbeat-proposal.md`](../outbox/operational-backup-heartbeat-proposal.md).

Решение владельца: **внешнюю cron-схему выпиливаем**, мониторинг бэкапов и видимости БД переносим внутрь бота (паттерн TASK-097). Физический `pg_dump`/ротацию оставляет контейнер `db-backup` (TASK-029) — он не трогается. Бот выступает **наблюдателем и докладчиком**.

> ⚠️ **Срочный ops-пункт (вне этой задачи, owner-direct):** убрать битый `/etc/cron.d/bettgbot-backup` с серверов и подтвердить, что контейнер `db-backup` реально пишет дампы. Это не код-задача — делает владелец на сервере.

## Цель

Ежечасный bot-джоб `send_backup_health_heartbeat`: проверяет доступность Postgres и Redis из инстанса бота и свежесть последнего бэкапа (по файлам в смонтированном volume), шлёт структурированный статус в `ADMIN_TELEGRAM_CHAT_IDS`; при просрочке/ошибке — явный алерт.

## Решения архитектора (ответы на вопросы proposal)

1. **Частота/флаг:** `CronTrigger(minute=7)` (ежечасно в :07, как в legacy). Включается флагом `BACKUP_HEARTBEAT_ENABLED` (env, **default `false`**). При `false` — джоб не регистрируется.
2. **Источник свежести бэкапа:** файлы в смонтированном volume (1-й этап) — берём новейший `*.sql.gz`, его `mtime` и размер. Таблицу `backup_run` **не** вводим сейчас (записано в backlog на будущее).
3. **Primary-guard:** отдельная машинерия `is_primary` не нужна. Джоб шлёт там, где `BACKUP_HEARTBEAT_ENABLED=true` — включаем флаг **только на том инстансе бота, где смонтирован backup-volume** (см. предпосылку ниже). Так нет дублей.
4. **Объём 1-й итерации:** видимость Postgres (через app `engine`, лёгкий `SELECT 1`) + Redis (`ping`) + возраст/размер последнего бэкапа + общий статус. Алерт, если возраст > `BACKUP_MAX_AGE_HOURS` (env, default `2`) или бэкапов нет, или БД/Redis недоступны.
5. **Старый `db-backup` контейнер:** оставляем как есть (продюсер дампов, второй уровень). Не трогаем.
6. **Тексты:** новые константы `OPERATIONAL_HEARTBEAT_*` в `src/bot/texts.py`.

## 🚩 Ключевая предпосылка по топологии (подтвердить при деплое)

Бэкапы пишутся на Admin-сервере в volume `bb-db-backups`. Чтобы джоб видел свежесть по файлам, **инстанс бота с `BACKUP_HEARTBEAT_ENABLED=true` должен работать на том же хосте и иметь этот volume смонтированным read-only**. Если бот живёт только на отдельном Bot-сервере (без доступа к backup-volume) — проверка свежести по файлам невозможна; тогда (вне этой задачи) поднять bot-инстанс на Admin-хосте ИЛИ перейти на таблицу `backup_run`. Видимость Postgres/Redis каждый инстанс проверяет свою.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-099-report.md`.

- [ ] `Settings`: `backup_heartbeat_enabled: bool` (env `BACKUP_HEARTBEAT_ENABLED`, default `false`), `backup_max_age_hours: int` (env `BACKUP_MAX_AGE_HOURS`, default `2`), `backup_dir: Path` (env `BACKUP_DIR`, default — путь mount, напр. `/backups`).
- [ ] Хелпер «свежесть бэкапа»: новейший `*.sql.gz` в `backup_dir` → возраст (по `mtime`, UTC) + размер; нет файлов → статус «нет бэкапов».
- [ ] Хелпер проверок: `SELECT 1` через app `engine` (с таймаутом), Redis `ping` (если Redis сконфигурирован).
- [ ] Джоб `send_backup_health_heartbeat(*, bot, session_maker)` в `jobs.py`: собирает статус, форматирует (тексты `OPERATIONAL_HEARTBEAT_*`), шлёт во все `ADMIN_TELEGRAM_CHAT_IDS`. Пустой список → `warning` + return. Ошибка отправки в один чат → `warning`, продолжаем.
- [ ] Регистрация в `builder.py` **только если** `backup_heartbeat_enabled`: `CronTrigger(minute=7)`, `id="send_backup_health_heartbeat"`, `coalesce=True`, `max_instances=1`, `misfire_grace_time` ~600.
- [ ] Compose: смонтировать backup-volume в сервис `bot` **read-only** (`bb-db-backups:/backups:ro` в prod-compose) + добавить env `BACKUP_HEARTBEAT_ENABLED`, `BACKUP_MAX_AGE_HOURS`, `BACKUP_DIR` в `.env.*example` и сервис `bot`. Дефолт выключено.
- [ ] Тесты с замоканным `Bot` и фейковой ФС/таймстампами: свежий бэкап → «ОК»; просроченный (> max_age) → алерт; нет файлов → алерт; БД/Redis недоступны → алерт; пустой `ADMIN_TELEGRAM_CHAT_IDS` → не шлёт; `backup_heartbeat_enabled=false` → джоб НЕ зарегистрирован (`test_builder`).
- [ ] `ruff` / `mypy src/shared` / `pytest` зелёные.
- [ ] PR `TASK-099: backup health heartbeat`; отчёт в outbox; move-семантика inbox→archive; ветка отребейзена на свежий `main` перед PR (иначе auto-merge не встанет).

## Артефакты

```
* src/shared/config.py                       # 3 новых поля
+ src/bot/_backup_health.py (или в jobs)     # хелперы freshness + ping
* src/bot/scheduler/jobs.py                  # send_backup_health_heartbeat
* src/bot/scheduler/builder.py               # условная регистрация
* src/bot/texts.py                           # OPERATIONAL_HEARTBEAT_*
* infra/docker-compose.prod*.yml, .env.*example
+ tests/unit/bot/scheduler/test_backup_heartbeat.py
```

## Ссылки

- Proposal: [`handoff/outbox/operational-backup-heartbeat-proposal.md`](../outbox/operational-backup-heartbeat-proposal.md)
- Паттерн джобов/отправки: TASK-097 (`send_daily_admin_digest`, `dispatch_event_result_notifications`)
- Бэкап-контейнер: `infra/docker-compose.prod*.yml` (`db-backup`, TASK-029)
- Решение: [`state/DECISIONS.md`](../../state/DECISIONS.md) (2026-06-01)

## Подсказки / не делать в этой задаче

- Таблица `backup_run`, проверка репликации на второй сервер, pending-alerts-файл как fallback — **отдельная итерация** (backlog), не сейчас.
- Создание дампов и ротацию НЕ переносить в бот — это остаётся в `db-backup`.
- `docs/`/`state/` не трогать — обновит cowork.
