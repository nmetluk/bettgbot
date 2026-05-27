---
id: TASK-039
completed: 2026-05-27
author: claude-opus-4.7
estimate: L → actual: L
related:
  - docs/audit/2026-05-25-mvp-audit.md (sec C-07)
  - handoff/inbox/TASK-039-offsite-encrypted-backup.md
---

# TASK-039: Offsite encrypted backup — отчёт

## Выполнено

### 1. BackupSettings в `src/shared/config.py`

- Добавлен класс `BackupSettings` с полями:
  - `enabled: bool = False` — выключен по умолчанию для dev
  - `age_recipient: str | None` — публичный ключ age
  - `rclone_remote: str | None` — rclone remote (B2/S3/etc)
  - `retention_days: PositiveInt = 30` — дней хранения
- Валидация: при `BACKUP_ENABLED=true` обязательно задать `age_recipient` и `rclone_remote`
- Интегрирован в `Settings` как `backup: BackupSettings`

### 2. Dockerfile.db-backup

- Создан `infra/Dockerfile.db-backup` на базе `postgres:16-alpine`
- Установлены `rclone` и `age` через `apk add --no-cache`
- Размер образа: ~270MB (240MB base + 30MB tools)

### 3. docker-compose.prod.yml

- `db-backup` сервис переписан для поддержки двух режимов:
  - **local-only** (BACKUP_ENABLED=false): pg_dump в local volume, cleanup через 14 дней
  - **offsite** (BACKUP_ENABLED=true): pg_dump | gzip | age → rclone copy → cleanup
- Файлы шифруются **перед** отправкой в offsite (age -r)
- rclone может быть настроен через env переменные (RCLONE_CONFIG_*)

### 4. Makefile цели

- `prod.backup.verify`: smoke-restore последнего offsite дампа
  - Ищет последнюю папку в RCLONE_REMOTE
  - Копирует, расшифровывает (через age -d), восстанавливает в БД
  - Требует age-private-key в `~/.config/age-backup-key.txt`
- `prod.backup.restore.offsite`: восстановление конкретного offsite дампа
  - Параметры: `FILE=timestamp/filename.sql.gz.age AGE_KEY_FILE=path/to/key.txt`

### 5. GitHub Actions workflow

- `.github/workflows/backup-verify.yml`:
  - Запускается каждое воскресенье в 03:00 UTC
  - Подключается к VPS по SSH
  - Выполняет `make prod.backup.verify`
  - Требует secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `REPO_PATH`

### 6. Документация

- `docs/07-deployment.md` обновлён:
  - Раздел "Шаг 6: Настройка offsite backup"
  - Инструкция по генерации age ключей
  - Настройка rclone (B2/S3/etc)
  - DR-сценарий восстановления (заглушка, подробности в TASK-042)

### 7. .env примеры

- `infra/.env.example`: добавлены `BACKUP_*` переменные с комментариями
- `infra/.env.prod.example`: заполнены `BACKUP_*` для prod

### 8. Unit тесты

- `tests/unit/test_config.py`: +8 тестов для BackupSettings
- Все 398 тестов проходят

## Выбор провайдера хранилища

**Оставлен на усмотрение владельца.** Рекомендации из документации:

| Провайдер | Стоимость | Примечания |
|------------|-----------|------------|
| Backblaze B2 | ~$6/TB/month | Простой в настройке, CLI-friendly |
| AWS S3 | varies | Если уже есть AWS аккаунт |
| Google Drive | free tier | Личный проект, но медленнее |
| S3-совместимые (Wasabi, DO) | varies | Альтернативы |

Для бэттинг-бота размер БД пока <100MB, поэтому стоимость будет **<$1/month**.

## Ссылки

- Commit: `5677d6a`
- Issue: (создать вручную, если нужен tracking)
- DR-runbook: будет оформлен в TASK-042

## Примечания

1. **Age private key** — должен храниться **только** у владельца, вне VPS. Без него восстановление невозможно.
2. **GitHub Actions** требует настройки secrets в repo settings перед первым запуском.
3. **Local volume backup** продолжает работать даже при `BACKUP_ENABLED=false` — fallback для dev.
4. **DR-runbook** (TASK-042) должен описать полное восстановление на новом VPS с нуля.
