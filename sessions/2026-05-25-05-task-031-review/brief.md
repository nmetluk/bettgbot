# Brief — task-031-review (Deploy README)

**Дата:** 2026-05-25
**Длительность:** короткая
**Участники:** Николай (owner), cowork-agent, локальный CC

## Что сделано в TASK-031

CC реализовал (squash `8edb6df`, PR #83; archive+report `63624fe`):

- `docs/07-deployment.md` расширен с 117 до ~300+ строк: требования к VPS, DNS, install Docker, clone repo, `.env` секреты, **двухфазный certbot bootstrap** (http-only nginx → `certonly` → full-TLS), `make prod.build`/`up`, `make prod.backup.now`, `make admin.create.prod`, проверка, регулярные операции, откат.
- `infra/nginx/admin-bootstrap.conf` — minimal http-only конфиг для шага certbot bootstrap.
- `Makefile`: добавлены цели `prod.certbot.init` и `admin.create.prod` (последний через `$(PROD_COMPOSE) exec -T web python scripts/create_admin.py`).

## Code review (cowork)

### Корректно

- `admin-bootstrap.conf` — правильный minimal config (listen 80 + `/.well-known/acme-challenge/` mount). ✓
- `admin.create.prod` — `exec -T web python scripts/create_admin.py` правильно (uv не нужен в prod, прямой python в контейнере). ✓
- README структурно полный — все 12 секций ToD выполнены, включая «Регулярные операции» и «Откат». ✓

### Блокер — `prod.certbot.init` возможно не запустит certbot

Makefile цель:

```makefile
$(PROD_COMPOSE) run --rm certbot certonly --webroot -w /var/www/certbot -d $$ADMIN_DOMAIN ...
```

Сервис `certbot` в `infra/docker-compose.prod.yml` имеет явный entrypoint:

```yaml
entrypoint: >
  sh -c "trap exit TERM;
         while :; do certbot renew --webroot -w /var/www/certbot --quiet;
                     sleep 12h & wait $${!}; done"
```

По compose docs, `run --rm <service> <args>` передаёт `<args>` **как command к existing entrypoint** (если entrypoint задан как exec form) или **аппендит к shell command** (если как shell form). С `entrypoint: >` (shell form) `certonly ...` уйдёт **как аргументы к `sh -c`**, не к `certbot`. То есть `prod.certbot.init` поднимет renew-loop вместо first issuance.

**Hotfix в этом cleanup:** добавлен `--entrypoint=""` в `run --rm certbot ...`. Это полностью обнуляет entrypoint, и command-line становится первым исполняемым:

```makefile
$(PROD_COMPOSE) run --rm --entrypoint="" certbot certbot certonly --webroot ...
```

(Double `certbot` — первый указывает что executable, второй — subcommand.)

### Workflow violation #4 подряд

CC снова оставил две копии TASK-031 в inbox после move в archive:

- `handoff/inbox/TASK-031-deploy-readme.md` (13033 bytes)
- `handoff/inbox/TASK-031.in-progress.md` (13033 bytes)

**Это четвёртый случай подряд** (TASK-028, 029, 030, 031). Усиления:
1. Explicit-секция в `handoff/README.md` (TASK-029 cleanup) — не сработало (CC не перечитывает README).
2. DoD-пункт с 🚨 в `handoff/templates/task.md` (TASK-030 cleanup) — не сработало (CC игнорирует пункт DoD).

**Сейчас:** переходим к **CI-check'у** (фиксировалось как fallback в TASK-030 decisions.md). Новый workflow `.github/workflows/handoff-consistency.yml` блочит merge в main, пока есть orphan'ы в inbox при существующем archive с тем же TASK-NNN. Это server-side enforcement, обойти нельзя.

### `make backup` не запускался — Drive отстал

Второй 🚨-пункт template'a CC тоже проигнорировал. Drive backup не содержит TASK-031 в archive. Cowork-агент сделал `make backup` сам в этом cleanup'e.

### Минор — report.md «walkthrough пройден мысленно»

CC написал: «README прошло мысленный walkthrough. Все команды копируемы и последовательны». Это **не реальный test** — настоящий walkthrough на dev-stack обнаружил бы блокер с `prod.certbot.init`. Пометил в тех-долге для шаблона report.md (требовать конкретные ручные тесты опасных путей).

## Hotfix-цикл (пятый подряд)

В составе этого cleanup'a перед TASK-032:

1. `git rm` двух копий TASK-031 в inbox.
2. **`.github/workflows/handoff-consistency.yml`** — новый CI-workflow с шагом `check-inbox-archive-consistency`. После merge cleanup'a будет блокировать любой PR в main с orphan'ами.
3. `Makefile prod.certbot.init`: добавлен `--entrypoint=""` для override.
4. `make backup` через cowork-канал.
5. Review-сессия TASK-031 (этот документ).
6. `state/PROJECT_STATUS.md` + `state/BACKLOG.md` — TASK-031 closed, TASK-032 в инбоксе.
7. `handoff/inbox/TASK-032-smoke-tests.md` — финальная задача MVP.

## Что осталось до MVP

Только **TASK-032** — smoke-тесты после деплоя (`scripts/smoke_test.sh` с curl на `/healthz` бота и админки, проверка alembic). После закрытия — MVP завершён, Этап 4 ✓, проект готов к выкатке на VPS.

## Решения этой сессии

См. `decisions.md` рядом. Одно новое:

- **CI-check на handoff consistency** как server-side enforcement workflow-инварианта. Локальные напоминания (README, template DoD) не работают — нужен hard block в pipeline.
