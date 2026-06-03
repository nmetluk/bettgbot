---
amends: TASK-103
created: 2026-06-03
author: cowork-agent
status: rework-requested
severity: CRITICAL (security regression in main)
---

# TASK-103 — дополнение (ЗАВЕРНУТО: security-регресс, срочная доработка)

## Что не так

Реализация (#224) **прямо нарушила ключевое требование задачи** и внесла дыру в безопасность, которая **уже в `main`**:

- Порты `5432:5432` и `6379:6379` **захардкожены прямо в `infra/docker-compose.prod.yml` И `infra/docker-compose.prod-no-domain.yml`** — биндятся на `0.0.0.0` (наружу), на **каждом** деплое.
- `prod-no-domain.yml` — это конфиг, который по своему же заголовку **«ТОЛЬКО ssh-tunnel, localhost, НЕ 0.0.0.0»** (закрытая сеть, TASK-047). Добавив туда публичный `5432`, мы выставили Postgres закрытого деплоя **в интернет**.
- **Firewall-скрипта в репозитории НЕТ** (есть только комментарий «MUST be firewalled»). То есть единственная «защита» — текст в YAML.

Исходная задача явно требовала обратное: *«НЕ хардкодить `ports:` в prod.yml/prod-no-domain.yml — одно-серверные деплои должны оставаться закрытыми; открыть = security-регресс. Добавить отдельный committed-overlay `expose-db.yml` + firewall.»* Это проигнорировано.

> 🚫 **До исправления не передеплоивать `prod.yml`/`prod-no-domain.yml`** — текущий коммит открывает БД наружу.

## Что сделать (рабочая версия)

- [ ] **Убрать `ports:` для `db` и `redis` из `infra/docker-compose.prod.yml` и `infra/docker-compose.prod-no-domain.yml`** (вернуть как было — закрыто).
- [ ] Создать **`infra/docker-compose.expose-db.yml`** (overlay) — только в нём `ports: ["5432:5432"]`/`["6379:6379"]`, с громким комментарием, что применяется ТОЛЬКО в split-топологии (отдельный воркер) и ТОЛЬКО вместе с firewall.
- [ ] Создать **реальный firewall-скрипт** `scripts/apply-bot-firewall.sh` (его сейчас нет в репо): DOCKER-USER правила — `ACCEPT` на 5432/6379 только с IP воркера (env `WORKER_IP`), `DROP` остального. Идемпотентно, с проверкой что цепочка применена.
- [ ] Запуск Admin в split-режиме: `-f prod.yml -f expose-db.yml` + обязательный прогон firewall-скрипта; в одно-серверном/no-domain режиме overlay НЕ подключается → БД закрыта.
- [ ] Текст для `docs/07-deployment.md` (в отчёт): split vs single-host, команда с overlay, обязательный firewall-шаг, **жирное предупреждение** «overlay без firewall = публичный Postgres».
- [ ] Проверка: `docker compose -f prod.yml config` НЕ содержит публичных `ports` для db/redis; `-f prod.yml -f expose-db.yml config` — содержит. `prod-no-domain.yml config` — db/redis закрыты.

## Условие закрытия
Дыра убрана из дефолтных compose, экспозиция вынесена в opt-in overlay + рабочий firewall-скрипт, no-domain снова закрыт. Зелёный CI, отчёт, archive, rebase на свежий main, явный auto-merge.
