---
id: TASK-042
created: 2026-05-25
author: external-auditor
parallel-safe: false
blockedBy:
  - TASK-039  # offsite backup должен быть рабочим, чтобы DR-runbook был достоверным
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: L
---

# TASK-042: DR-runbook + image-tagging в GHCR + manual-approval CD

## Контекст

Аудит MVP 2026-05-25, находка **C-10 + F-56 + F-63**. Деплой полностью ручной (`git pull && make prod.build && make prod.up` через ssh). Никакого confirmation deployed-version == main, никакого автоматического smoke после деплоя. Rollback = `git checkout <prev-sha> && make prod.build` (5-15 мин downtime). DR-runbook не существует — «как поднять с нуля на новом VPS» нигде не задокументировано.

## Цель

1. **Image-tagging**: образы bot/web билдятся в CI, пушатся в `ghcr.io/nmetluk/bettgbot-{bot,web}:${{ github.sha }}` + tag `latest`.
2. **Compose использует registry**: `infra/docker-compose.prod.yml` подтягивает `image: ghcr.io/.../bot:${IMAGE_TAG}` вместо локального build. `IMAGE_TAG` из `.env`.
3. **Deploy workflow** с manual approval: после merge в main → build+push → manual approval → ssh deploy → smoke. Rollback = бамп `IMAGE_TAG` обратно.
4. **DR-runbook** (`docs/runbook-dr.md`) — пошагово как поднять проект с нуля на новом VPS, восстановить БД из offsite-backup, обновить DNS.

## Definition of Done

- [ ] `.github/workflows/build-images.yml` (новый):
  - Trigger: `push: branches: [main]`, `workflow_dispatch`.
  - Job `build-bot`: `docker/build-push-action@v6` для `infra/Dockerfile.bot` → `ghcr.io/nmetluk/bettgbot-bot:${sha}` + `:latest`.
  - Job `build-web`: то же для `infra/Dockerfile.web`.
  - Используется `GITHUB_TOKEN` с `packages: write` permission.
- [ ] `.github/workflows/deploy-prod.yml` (новый):
  - Trigger: `workflow_dispatch` + опционально `release: { types: [published] }`.
  - Environment: `production` (с required reviewers — настройка через GitHub UI).
  - Step 1: SSH на VPS → `cd /opt/bettgbot && git pull && echo "IMAGE_TAG=${{ github.sha }}" >> .env`.
  - Step 2: `docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml pull && up -d`.
  - Step 3: `make prod.smoke` — fail = rollback.
  - Step 4 (rollback): если smoke red → revert `IMAGE_TAG` к previous, `up -d` опять.
- [ ] `infra/docker-compose.prod.yml`:
  - `bot`: убрать `build:`, заменить на `image: ghcr.io/nmetluk/bettgbot-bot:${IMAGE_TAG:-latest}`.
  - `web`: то же.
  - Прокинуть `IMAGE_TAG` через `.env`.
- [ ] `infra/.env.example` + `.env.prod.example` — добавить `IMAGE_TAG=latest`.
- [ ] `Makefile`:
  - `make prod.deploy IMAGE_TAG=<sha>` — локальная команда: установить IMAGE_TAG в .env, pull, up, smoke.
  - `make prod.rollback IMAGE_TAG=<prev-sha>` — обратное.
- [ ] `docs/runbook-dr.md` (новый) — пошаговый сценарий:
  ```
  ## Сценарий 1: VPS физически потерян
  1. Заказать новый VPS (Ubuntu 24.04 LTS, ≥2 GB RAM, ≥40 GB SSD).
  2. Установить Docker + Compose plugin (ссылка на 07-deployment.md).
  3. Клонировать `git clone https://github.com/nmetluk/bettgbot /opt/bettgbot`.
  4. Восстановить `.env` из keychain владельца / SOPS.
  5. Установить rclone + age, восстановить keys.
  6. Найти последний offsite-backup: `rclone ls b2:bettgbot-backups/ | tail -1`.
  7. `make prod.backup.restore.offsite FILE=<latest>`.
  8. `make prod.up && make prod.smoke`.
  9. Обновить DNS A-запись на новый IP VPS.
  10. Проверить TLS-сертификат — `make prod.certbot.init` если новый домен.
  Целевой RTO: ≤8h. Целевой RPO: ≤24h (зависит от частоты offsite-backup).
  ```
  ```
  ## Сценарий 2: БД повреждена (например, миграция)
  1. `docker compose -f .. stop bot web` — остановить writers.
  2. `make prod.backup.restore FILE=<last-good>` — local volume restore.
  3. `alembic current` — убедиться, что миграция применена.
  4. `make prod.up` + `make prod.smoke`.
  ```
  ```
  ## Сценарий 3: Откат deploy (плохая версия)
  Используй `make prod.rollback IMAGE_TAG=<previous-sha>`.
  ```
- [ ] Документ покрывает: RTO/RPO targets, contact-info владельца, перечень критичных секретов и где они хранятся.
- [ ] Smoke-test расширен: проверка `docker exec web alembic current` — должно совпадать с heads. Проверка TLS-cert expiry (`openssl s_client -connect ... -checkend 604800`).
- [ ] PR в GitHub, имя `TASK-042: image-tagging + deploy workflow + DR runbook`.
- [ ] Отчёт в `handoff/outbox/TASK-042-report.md`.
- [ ] **🚨 Move-семантика + `make backup`**.

## Артефакты

- `+ .github/workflows/build-images.yml`
- `+ .github/workflows/deploy-prod.yml`
- `* infra/docker-compose.prod.yml` — `image:` вместо `build:`
- `* infra/.env.example` + `.env.prod.example` — `IMAGE_TAG`
- `* Makefile` — `prod.deploy`, `prod.rollback`
- `+ docs/runbook-dr.md` — новый
- `* scripts/smoke_test.sh` — TLS + alembic checks
- `* docs/07-deployment.md` — обновить, сослаться на runbook-dr

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — C-10 + F-56 + F-63
- GHCR: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- GitHub Environments + manual approval: https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment

## Подсказки

- GHCR + private package требует `packages: write` permission в job-level, плюс `GITHUB_TOKEN` (не PAT).
- Тэг `:latest` — для удобства; для production `IMAGE_TAG` в .env должен быть **явный SHA**, чтобы знать какая версия в проде.
- SSH-deploy через `appleboy/ssh-action` — настройка SSH key как `${{ secrets.PROD_SSH_KEY }}`; владельцу инструкция как создать.
- Альтернатива manual-approval: watchtower — auto-deploy при появлении новой `:latest`. **Не рекомендую** для prod — слишком мало контроля.
- DR-runbook должен быть **executable** — реально пройти через все шаги в staging-окружении перед закрытием задачи (smoke-test самого runbook).
