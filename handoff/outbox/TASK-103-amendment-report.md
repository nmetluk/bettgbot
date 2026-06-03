---
task: TASK-103-amendment
completed: 2026-06-04
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/234
branch: feature/TASK-103-amendment-ports-firewall
commits:
  - chore(infra): revert hardcoded db/redis ports from prod ymls (TASK-103 amendment)
  - feat(infra): add expose-db.yml overlay + apply-bot-firewall.sh + env comments (TASK-103 security fix)
---
# Отчёт по TASK-103 amendment: Исправление security-регресса с портами БД/Redis (expose overlay + firewall)

## Сводка

Предыдущая реализация TASK-103 (permanent ports для worker) была ЗАВЕРНУТА cowork-агентом как CRITICAL security regression: порты 5432/6379 были захардкожены в `docker-compose.prod.yml` и `prod-no-domain.yml` (бИНД 0.0.0.0), без реального firewall-скрипта в репо (только комментарий). Это выставляло Postgres/Redis "закрытого" (no-domain, TASK-047) и обычного прод-деплоя в интернет, противореча исходному требованию задачи ("НЕ хардкодить ports в prod.yml — использовать отдельный overlay + firewall").

Выполнено строго по "рабочая версия" из amendment:

- Убраны `ports:` для db/redis + все TASK-103-комментарии из обоих prod yml (дефолт — закрыто).
- Создан `infra/docker-compose.expose-db.yml` — чистый opt-in overlay, который добавляет порты. Громкие DANGER-комментарии: ТОЛЬКО split (Admin+worker), ТОЛЬКО вместе с firewall-скриптом, НИКОГДА на single-host / no-domain.
- Создан `scripts/apply-bot-firewall.sh` (+x): идемпотентная настройка DOCKER-USER (iptables): ACCEPT 5432/6379 только с $WORKER_IP, DROP для остальных. С подробным header-usage, проверками, примерами persistence.
- Обновлены `.env*.example` (prod, example, bot) — добавлен WORKER_IP с объяснением и ссылками.
- Обновлены комментарии в Makefile (PROD_COMPOSE, PROD_NO_DOMAIN_COMPOSE) с примерами использования overlay + обязательным шагом firewall.
- Подготовлен текст для вставки в `docs/07-deployment.md` (см. ниже) — описание split-топологии, команд, предупреждений.
- Верификация `docker compose ... config` (дефолт без портов; с overlay — с портами; no-domain — без).
- Полный DoD (ruff check + format --check, mypy src/shared, pytest) — зелёный (изменения только infra + sh, python-часть не тронута).

Всё соответствует CLAUDE.md / handoff (rebase, отчёт до archive-коммита, PR с auto-merge, и т.д.). Не передеплоивать старые prod.yml до фикса (как указано в amendment).

## Изменённые файлы

```
* infra/docker-compose.prod.yml             # removed db/redis ports + TASK-103 comments (closed by default)
* infra/docker-compose.prod-no-domain.yml   # same (no-domain stays closed)
+ infra/docker-compose.expose-db.yml        # NEW: opt-in overlay with loud warnings (ONLY split + firewall)
+ scripts/apply-bot-firewall.sh             # NEW: idempotent DOCKER-USER whitelist script (WORKER_IP), +x
* infra/.env.prod.example                   # + WORKER_IP comment + cross-refs
* infra/.env.example                        # + WORKER_IP note
* infra/.env.bot.example                    # + note (not needed on worker, but for completeness)
* Makefile                                  # comments for PROD_COMPOSE + expose overlay usage + firewall step
+ handoff/outbox/TASK-103-amendment-report.md
```

(Также удалён/перемещён inbox/TASK-103-amendment.in-progress.md → archive в handoff-коммите.)

## Как воспроизвести / запустить

```bash
# 1. Переключиться (после pull)
git checkout feature/TASK-103-amendment-ports-firewall

# 2. Верификация (как в amendment + DoD)
# Дефолт (без overlay) — портов для db/redis НЕТ
POSTGRES_USER=dummy POSTGRES_PASSWORD=dummy POSTGRES_DB=dummy ADMIN_DOMAIN=ex.com TLS_EMAIL=a@b.c \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml config \
  | sed -n '/^  db:/,/^  redis:/p' | grep -E 'ports:|5432|6379' || echo 'NO ports in default — GOOD (closed)'

# С overlay — порты ЕСТЬ (только для split)
POSTGRES_USER=dummy POSTGRES_PASSWORD=dummy POSTGRES_DB=dummy ADMIN_DOMAIN=ex.com TLS_EMAIL=a@b.c \
  docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml -f infra/docker-compose.expose-db.yml config \
  | sed -n '/^  db:/,/^  redis:/p' | grep -E 'ports:|5432|6379' && echo 'ports present with overlay — GOOD'

# no-domain остаётся закрытым
... аналогично для prod-no-domain.yml ...

# 3. Firewall (на "Admin" хосте; в этом env просто проверить синтаксис)
WORKER_IP=1.2.3.4 bash -n scripts/apply-bot-firewall.sh && echo 'script syntax OK'
# Реальный запуск требует root + iptables + WORKER_IP; в контейнере/CI — только проверка.

# 4. Полный DoD (обязательно перед PR)
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/shared
uv run pytest -q --tb=no

# 5. Пример деплоя split (документировано в compose overlay и в prepared text ниже)
# На Admin:
#   WORKER_IP=195.133.26.200 sudo scripts/apply-bot-firewall.sh
#   docker compose -f ...prod.yml -f ...expose-db.yml up -d
# На worker: обычный bot-only (без expose).
```

## Что не сделано (если применимо)

- Не редактировал `docs/07-deployment.md` напрямую (по CLAUDE.md правило "не менять docs/ без явного указания"; amendment требует только "Текст для ... (в отчёт)" — подготовил ниже, cowork вставит).
- Не добавлял WORKER_IP в реальные .env (они в .gitignore); только примеры + комментарии.
- Firewall-скрипт — только iptables v4 + DOCKER-USER (самый распространённый случай). IPv6 / firewalld / ufw — оставлено на deploy-скрипты владельца (можно расширить позже).
- Не сделал systemd unit / rc.local авто-применения — это часть деплоя/оркестрации (в report текст + пример в header скрипта).
- Не трогал state/, другие docs, кроме подготовки текста. Не менял поведение single-host / no-domain (они остаются закрытыми).
- Не обновлял существующий feature/TASK-103-ports-permanent (оставил как исторический rejected); новая ветка для amendment.
- Полный персистентный firewall на реальном проде — требует доп. работы владельца (iptables-persistent или deploy hook).

## Открытые вопросы для проектировщика

- Нет критических. Всё по amendment закрыто.
- (Мелочь) Стоит ли добавить в Makefile отдельную переменную EXPOSE_DB_COMPOSE и цель prod.firewall (чтобы make мог автоматизировать)? Можно в следующем infra-таске, если нужно. Сейчас достаточно комментариев + явных команд в compose (как в amendment).
- (Для владельца) После merge — обновить реальные сервера: убрать expose из текущих запущенных compose (если применяли), применить overlay только после firewall + WORKER_IP.

## Предложение для PROJECT_STATUS.md

- 2026-06-04 — TASK-103 amendment (rework): security regression исправлен. Порты db/redis убраны из дефолтных prod.yml / prod-no-domain.yml. Добавлен opt-in `docker-compose.expose-db.yml` (только split + firewall). Создан `scripts/apply-bot-firewall.sh` (идемпотентный whitelist по WORKER_IP в DOCKER-USER). Обновлены .env.example + Makefile комментарии. Подготовлен текст для docs/07. CI (ruff/format/mypy/pytest) зелёный. (PR #XXX)

## Текст для docs/07-deployment.md (предлагаемый для вставки)

(Вставить в раздел про split / multi-host / worker, после описания bot-only и replication (TASK-100/101/108), или как новый подраздел "Split-host: exposing DB/Redis safely (TASK-103 amendment)". После "Permanent paths for replication".)

### Split-host topology: exposing Postgres/Redis for worker (TASK-103 amendment)

В split-деплое (отдельный Admin + dedicated worker bot) воркер должен иметь доступ к БД/Redis на Admin для репликации бэкапов (TASK-100) и других операций.

**По умолчанию порты закрыты** (в `docker-compose.prod.yml` и `prod-no-domain.yml` после TASK-103 amendment). Это исправляет предыдущий security-регресс (порты были открыты на 0.0.0.0 без реального файрвола).

**Для split используйте overlay + firewall (opt-in):**

1. На Admin хосте настройте WORKER_IP (IP воркера):
   ```bash
   # в .env (или .env.prod)
   WORKER_IP=195.133.26.200
   ```

2. Примените файрвол ( whitelist только воркер; всё остальное DROP ):
   ```bash
   sudo scripts/apply-bot-firewall.sh
   ```
   Скрипт идемпотентен, работает с DOCKER-USER. Запускайте после ребутов / docker restart.

3. Поднимите Admin с overlay:
   ```bash
   docker compose \
     -f infra/docker-compose.yml \
     -f infra/docker-compose.prod.yml \
     -f infra/docker-compose.expose-db.yml \
     --env-file .env up -d
   ```

**Проверка:**
```bash
# без overlay — портов нет (закрыто)
docker compose -f ...prod.yml config | grep -E '5432|6379' || echo closed

# с overlay — порты есть
docker compose -f ...prod.yml -f ...expose-db.yml config | grep -E '5432|6379'
```

**no-domain / single-host:**
- Используйте `prod-no-domain.yml` или обычный `prod.yml` **без** `expose-db.yml` — БД остаётся закрытой (ssh-tunnel или localhost).
- Добавление overlay на no-domain = нарушение дизайна (TASK-047).

**⚠️ КРИТИЧНО:**
- Overlay без запущенного firewall-скрипта = Postgres/Redis публичны в интернет (CRITICAL).
- WORKER_IP обязателен и должен быть точным.
- Скрипт + overlay — только на Admin в split-топологии.
- См. `infra/docker-compose.expose-db.yml` (полные комментарии), `scripts/apply-bot-firewall.sh` (header с примерами persistence), `.env.prod.example`.

После применения — worker (bot-only) сможет подключаться по `ADMIN_DOMAIN:5432` / `:6379` (или IP).

## Метрики (опционально)

- 8 файлов (в основном infra + 1 sh).
- Security hole закрыта, соответствие исходному замыслу TASK-103 + TASK-047.
- 0 изменений в src/ — только инфраструктура и примеры.
- Полные проверки зелёные.