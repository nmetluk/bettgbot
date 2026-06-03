---
id: TASK-103
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/backup-replication-deployment-audit-2026-06-03.md
  - infra/docker-compose.prod.yml
  - docs/07-deployment.md
priority: high
estimate: M
---

# TASK-103: Публикация портов Postgres/Redis для двухсерверной топологии (split)

## Контекст

Деплой-аудит 2026-06-03 (PR #214) показал: воркер-бот на отдельном сервере (195.133.26.200) **не мог достучаться** до Postgres/Redis Admin-сервера (5.188.88.78) — `Connection refused`. Причина: коммитнутые `infra/docker-compose.prod.yml` и `infra/docker-compose.prod-no-domain.yml` **не публикуют** порты db/redis (`docker port` → `5432/tcp -> None`); порты есть только в dev-override на `127.0.0.1`. Из-за этого ломались **все** DB-зависимые джобы воркера: напоминания, пост-итоговые сводки, heartbeat, репликация. Деплой-команда временно открыла порты через **некоммитнутый** `/tmp/db-ports-override.yml` — это не переживёт пересоздание контейнеров.

Это мой (архитектора) недосмотр в дизайне TASK-100: cross-server чтение `backup_run`/работа джобов требует сетевого доступа воркера к БД, а compose его не открывал.

## Цель

Дать **повторяемый, безопасный** способ опубликовать порты Postgres/Redis для split-топологии — не открывая БД в одно-серверных деплоях по умолчанию.

## Решение (архитектор)

- **НЕ** хардкодить `ports:` в `prod.yml`/`prod-no-domain.yml` — одно-серверные деплои должны оставаться закрытыми (БД и бот на одном хосте, наружу 5432 не нужен; открыть = security-регресс).
- Добавить **отдельный committed-overlay** `infra/docker-compose.expose-db.yml`:
  ```yaml
  services:
    db:
      ports: ["5432:5432"]
    redis:
      ports: ["6379:6379"]
  ```
  Применяется только в split-деплое Admin-сервера: `-f prod.yml -f expose-db.yml`.
- **Firewall обязателен и первичен.** Открытие порта валидно ТОЛЬКО вместе с DOCKER-USER-whitelist (разрешить вход на 5432/6379 исключительно с IP воркера, drop для всех остальных). Есть `scripts/apply-bot-firewall.sh` (или эквивалент) — задействовать/дописать, чтобы overlay без применённого firewall не оставлял Postgres открытым в интернет.

## Definition of Done

> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-103-report.md`.

- [ ] `infra/docker-compose.expose-db.yml` — overlay с `ports` для db/redis, с большим комментарием-предупреждением про обязательный firewall-whitelist.
- [ ] `scripts/apply-bot-firewall.sh` — проверить/дописать: DOCKER-USER правила, разрешающие 5432/6379 только с IP воркера (env `WORKER_IP`/`BACKUP_SOURCE`-аналог), явный drop остального. Идемпотентно.
- [ ] `docs/07-deployment.md` — раздел «Двухсерверная топология (Admin + Worker)»: команда запуска Admin с overlay, обязательный firewall-шаг, проверка `docker port` + TCP-коннект с воркера. **Громкое предупреждение:** overlay без firewall = публичный Postgres.
- [ ] Не трогать одно-серверный путь (no-domain) — там порты остаются закрытыми.
- [ ] `ruff`/`mypy`/`pytest` зелёные (инфра-правки кода не трогают, но прогнать); PR, отчёт, move inbox→archive, rebase на свежий main, явный auto-merge.

## Артефакты
```
+ infra/docker-compose.expose-db.yml
* scripts/apply-bot-firewall.sh         (или создать, если отсутствует)
* docs/07-deployment.md                 (зона cowork — НЕ трогать; см. ниже)
```
> `docs/07-deployment.md` — зона проектировщика. Исполнителю: подготовь **текст** раздела в отчёте, cowork впишет в doc. Сам doc не редактируй.

## Ссылки
- Аудит: [`handoff/outbox/backup-replication-deployment-audit-2026-06-03.md`](../outbox/backup-replication-deployment-audit-2026-06-03.md)
- Топология: TASK-100, `pinbetting.txt` (на сервере)
