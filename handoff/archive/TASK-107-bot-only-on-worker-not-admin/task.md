---
id: TASK-107
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/TASK-105-report.md
  - infra/docker-compose.prod.yml
  - infra/docker-compose.prod-no-domain.yml
priority: high
estimate: S
---

# TASK-107: Бот — только на воркере, не на Admin (repo-фикс топологии)

## Контекст

Диагностика TASK-105 показала, что `bettgbot-bot-1` крутится **и на Admin (5.188.88.78), и на воркере (195.133.26.200)**. Владелец подтвердил: **бот на Admin — ошибка.** Бот должен работать только на выделенном воркере (у Admin к тому же нет egress в Telegram → его инстанс шлёт в никуда + дублирует scheduler-работу). На сервере бот с Admin снимается в рамках TASK-106; здесь — **постоянный фикс в репозитории**, чтобы Admin-деплой больше не поднимал `bot`.

## Цель

Admin-композиция запускает только инфраструктуру и web (`db`, `redis`, `db-backup`, `web`, `nginx`, ...), **без сервиса `bot`**. Бот поднимается отдельно воркерным compose (TASK-104, `docker-compose.bot-only.yml`).

## Definition of Done

> 🚨 Перед archive — `handoff/outbox/TASK-107-report.md`.

- [ ] Разобраться, как `bot` сейчас попадает в Admin-запуск (профиль `full`? отдельный сервис без профиля в `prod.yml`/`prod-no-domain.yml`?), и сделать так, чтобы **штатная команда запуска Admin не поднимала `bot`**:
  - предпочтительно — вынести `bot` под отдельный compose-профиль (напр. `profiles: ["bot"]`) или в отдельный файл, который на Admin не подключается;
  - либо явно задокументировать команду запуска Admin без `bot` и убрать `bot` из дефолтного набора.
- [ ] Гарантировать, что `db`/`redis`/`db-backup`/`web`/`nginx` на Admin поднимаются как раньше (бот не тянется транзитивно через `depends_on`).
- [ ] Текст для `docs/07-deployment.md` (в отчёт, doc впишет cowork): Admin = инфра+web, Worker = bot-only; явные команды запуска для каждого сервера.
- [ ] Проверка: `docker compose -f <admin-набор> config --services` **не** содержит `bot`; воркерный `bot-only.yml` поднимает `bot`.
- [ ] `ruff`/`mypy`/`pytest` зелёные (инфра, кода не трогает — прогнать); PR, отчёт, move inbox→archive, rebase на свежий main, явный auto-merge.

## Артефакты
```
* infra/docker-compose.prod.yml            (вынести/гейтить сервис bot)
* infra/docker-compose.prod-no-domain.yml  (то же; учесть, что no-domain может быть single-host)
```
> Внимание: для **одно-серверного** no-domain-деплоя бот и инфра на одном хосте — там бот нужен. Реши аккуратно: профиль/overlay, чтобы split-Admin бота не поднимал, а single-host — поднимал. Обоснуй выбор в отчёте.

## Ссылки
- Диагностика: [`handoff/outbox/TASK-105-report.md`](../outbox/TASK-105-report.md)
- Воркер-compose: TASK-104
