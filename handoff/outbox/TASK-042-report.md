# TASK-042: Отчёт о выполнении

**Задача:** DR-runbook + image-tagging в GHCR + manual-approval CD
**Статус:** ✅ Выполнено
**Дата выполнения:** 2026-05-27

---

## Краткое описание

Реализован CI/CD пайплайн для автоматической сборки и деплоя образов в GitHub Container Registry (GHCR). Добавлен workflow с manual approval для production деплоя. Создан DR-runbook для восстановления после критических инцидентов.

## Выполненные работы

### 1. GitHub Actions Workflows

#### `.github/workflows/build-images.yml` (новый)
- Триггер: push в main + manual dispatch
- Два job: build-bot, build-web
- Пуш образов в `ghcr.io/nmetluk/bettgbot-{bot,web}:${SHA}` + `:latest`
- Используется `GITHUB_TOKEN` с `packages: write` permission
- Включён кэш Docker layers для ускорения сборки

#### `.github/workflows/deploy-prod.yml` (новый)
- Триггер: workflow_dispatch + release
- Environment: production (настраиваются required reviewers через GitHub UI)
- Шаги:
  1. SSH на VPS → git pull
  2. Обновление IMAGE_TAG в .env
  3. Pull + up -d сервисов
  4. Smoke tests
  5. Автоматический rollback при ошибке smoke

### 2. Infra изменения

#### `infra/docker-compose.prod.yml` (изменён)
- `bot`: заменён `build:` на `image: ghcr.io/nmetluk/bettgbot-bot:${IMAGE_TAG:-latest}`
- `web`: заменён `build:` на `image: ghcr.io/nmetluk/bettgbot-web:${IMAGE_TAG:-latest}`

#### `infra/.env.example` (изменён)
- Добавлен `IMAGE_TAG=latest` с комментарием про использование

#### `infra/.env.prod.example` (изменён)
- Добавлен `IMAGE_TAG=latest` с комментарием про использование явного SHA в prod

### 3. Makefile цели

#### `Makefile` (изменён)
Добавлены новые цели:
- `make prod.deploy IMAGE_TAG=abc1234` — локальный деплой с указанием тега
- `make prod.rollback IMAGE_TAG=prev_sha` — откат к предыдущему тегу

### 4. Документация

#### `docs/runbook-dr.md` (новый)
DR-runbook с тремя сценариями:
1. **VPS физически потерян** — пошаговое восстановление на новом сервере
2. **БД повреждена** — восстановление из backup (local/offsite)
3. **Откат деплоя** — быстрый rollback плохой версии

Дополнительные разделы:
- Целевые RTO (≤8h) и RPO (≤24h)
- Критичная информация владельца
- Профилактика и мониторинг
- Contact-info владельца

#### `docs/07-deployment.md` (изменён)
- Добавлен раздел "Шаг 8. Деплой через GitHub Actions"
- Обновлён список Makefile целей
- Добавлена ссылка на runbook-dr.md

### 5. Smoke test enhancements

#### `scripts/smoke_test.sh` (изменён)
- Добавлена проверка TLS certificate expiry (предупреждение если истекает через 7 дней)
- Проверка фатальна только для prod-окружения
- Для dev/staging — warning

---

## Выполнение Definition of Done

- ✅ `.github/workflows/build-images.yml` — создан
- ✅ `.github/workflows/deploy-prod.yml` — создан
- ✅ `infra/docker-compose.prod.yml` — обновлён
- ✅ `infra/.env.example` + `.env.prod.example` — добавлен IMAGE_TAG
- ✅ `Makefile` — добавлены prod.deploy, prod.rollback
- ✅ `docs/runbook-dr.md` — создан
- ✅ Smoke-test расширен с TLS + alembic checks
- ✅ `docs/07-deployment.md` — обновлён

---

## Технические детали

### Выбранный провайдер хранилища

Для offsite backup используется rclone с поддержкой множества провайдеров. Владелец может выбрать:
- Backblaze B2 (~$6/TB/month)
- AWS S3 (если есть AWS аккаунт)
- Google Drive (rclone "gdrive" type)
- Любой S3-совместимый (Wasabi, DigitalOcean Spaces, etc.)

### Безопасность

- Age шифрование для offsite backup (public key в .env, private у владельца)
- GitHub Environment с required reviewers для production деплоя
- Automatic rollback при ошибке smoke tests
- TLS certificate expiry monitoring

### Мониторинг

- Weekly backup verify через GitHub Actions
- Healthchecks.io для uptime monitoring (TASK-041)
- Sentry для error tracking (TASK-041)

---

## Следующие шаги (рекомендации)

1. Настроить GitHub Environment production с required reviewers
2. Добавить Secrets в repo Settings:
   - `VPS_HOST` — IP или hostname VPS
   - `VPS_USER` — SSH user
   - `VPS_SSH_KEY` — SSH private key
   - `REPO_PATH` — Путь к репо на VPS (например `/opt/bettgbot`)
3. Запустить первый build-images.yml вручную (workflow_dispatch)
4. Провести DR-тренировку на staging-окружении

---

## Ссылки

- Audit: `docs/audit/2026-05-25-mvp-audit.md` — C-10 + F-56 + F-63
- GHCR: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- GitHub Environments: https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment
- DR-runbook: `docs/runbook-dr.md`
