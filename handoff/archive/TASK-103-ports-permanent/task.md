---
id: TASK-103
created: 2026-06-03
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - handoff/outbox/TASK-105-report.md
  - handoff/archive/TASK-106-prod-notification-delivery-round2/task.md
  - infra/docker-compose.prod.yml
  - infra/docker-compose.prod-no-domain.yml
priority: high
estimate: S
---

# TASK-103: Постоянные порты DB/Redis для worker (в prod compose)

## Контекст

Из прод-аудита TASK-105 и TASK-106: worker bot не может достучаться до DB/Redis на Admin (Connection refused на 5.188.88.78:5432/6379). Порты никогда не публиковались в прод-композах (только dev override на 127.0.0.1). Временно использовали /tmp override + docker up.

В TASK-106/task.md указано как отдельный infra-фикс (не на проде): TASK-103 (порты), TASK-104 (воркер-compose/права).

## Цель

Добавить `ports:` для db (5432) и redis (6379) в `infra/docker-compose.prod.yml` и `prod-no-domain.yml` навсегда, с комментариями про firewall.

## Definition of Done

- [ ] Порты добавлены в оба prod*.yml под db и redis.
- [ ] Комментарии с отсылкой к аудитам TASK-105, firewall DOCKER-USER, worker IP, и текст для docs/07-deployment.md.
- [ ] `docker compose -f base -f prod.yml config` показывает порты под db/redis; admin-набор не тянет bot (совместимо с TASK-107).
- [ ] Отчёт в outbox/TASK-103-report.md с текстом для docs.
- [ ] PR, auto-merge, archive (даже если task.md не был в inbox изначально — реконструирован по ссылкам).

## Артефакты

* infra/docker-compose.prod.yml
* infra/docker-compose.prod-no-domain.yml

## Ссылки

- Аудит: handoff/outbox/TASK-105-report.md
- План: handoff/archive/TASK-106-.../task.md
