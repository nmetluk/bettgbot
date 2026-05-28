# 07 — Деплой на VPS

Полное руководство по выкладке Betting Bot на Ubuntu VPS с Docker Compose.

## Требования к VPS

- **ОС:** Ubuntu 24.04 LTS (другие Debian-based тоже подойдут, команды могут незначительно отличаться)
- **Ресурсы:** 1 vCPU, 1-2 GB RAM, 20 GB SSD
- **Порты:** 80 (HTTP), 443 (HTTPS) — открыты извне
- **Доступ:** SSH по ключу

## DNS

Создайте A-запись `your-domain.com` → IP VPS в панели регистратора домена. Проверьте распространение:

```bash
nslookup your-domain.com
```

## Шаг 1. Установка зависимостей

SSH на VPS и установите Docker, Docker Compose, git, make:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2-plugin git make
sudo systemctl enable docker
sudo systemctl start docker
```

Проверьте:

```bash
docker --version
docker compose version
```

## Шаг 2. Клонирование репо

```bash
sudo mkdir -p /opt/bettgbot
sudo chown $USER:$USER /opt/bettgbot
git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot
cd /opt/bettgbot
```

## Шаг 3. Настройка `.env`

Скопируйте prod-пример и заполните ОБЯЗАТЕЛЬНЫЕ поля:

```bash
cp infra/.env.prod.example infra/.env
nano infra/.env
```

⚠️ **ВАЖНО:** Приложение на старте проверяет, что в prod все секреты являются сильными. Если используете дефолтные значения (`dev-admin-secret`, `changeme`, и т.п.) — старт прервётся с понятной ошибкой.

### Сегрегация секретов по сервисам

Каждый контейнер получает только те переменные, которые ему нужны. Это достигается через явные `environment:` блоки в `docker-compose.yml` (и его prod-вариантах) вместо общего `env_file:`.

- `bot` → получает `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`, переменные external registry
- `web` → получает `DATABASE_URL`, `REDIS_URL`, `ADMIN_SECRET_KEY`, `ADMIN_CSRF_SECRET`
- `db-backup` → получает только `POSTGRES_*` и `BACKUP_*` переменные

См. `infra/.env.bot.example`, `infra/.env.web.example`, `infra/.env.db.example` для справки по минимальным наборам.

**Генерация сильных секретов:**

Все секреты генерируйте локально (не на VPS) и копируйте в `.env`:

```bash
# Сгенерировать все секреты разом:
python -c "
import secrets
print('TELEGRAM_BOT_TOKEN=<получить у @BotFather>')
print(f'POSTGRES_PASSWORD={secrets.token_urlsafe(32)}')
print(f'ADMIN_SECRET_KEY={secrets.token_urlsafe(64)}')
print(f'ADMIN_CSRF_SECRET={secrets.token_urlsafe(64)}')
print(f'EXTERNAL_API_TOKEN={secrets.token_urlsafe(32)}')
"
```

**Обязательные переменные для prod:**

| Переменная | Описание | Требования |
|---|---|---|
| `ENVIRONMENT` | Окружение | `prod` (обязательно) |
| `TELEGRAM_BOT_TOKEN` | Token от @BotFather | Реальный токен (≥35 символов) |
| `POSTGRES_PASSWORD` | Пароль БД | Сгенерированный (≥32 символов) |
| `ADMIN_SECRET_KEY` | Секрет сессии админки | Сгенерированный (≥32 символов) |
| `ADMIN_CSRF_SECRET` | Секрет CSRF | Сгенерированный (≥32 символов) |
| `EXTERNAL_REGISTRY_BACKEND` | Реестр пользователей | `http` (НЕ `mock`) |
| `EXTERNAL_API_BASE_URL` | URL реестра | Реальный https URL |
| `EXTERNAL_API_TOKEN` | Токен реестра | Сгенерированный |
| `LOG_FORMAT` | Формат логов | `json` (обязательно для prod) |
| `ADMIN_DOMAIN` | Домен админки | `your-domain.com` |
| `TLS_EMAIL` | Email для Let's Encrypt | `your@email.com` |

**Запрещённые значения в prod:**

Секреты НЕ должны содержать подстроки: `dev-`, `changeme`, `secret`, `test`.
Длина секретов должна быть ≥32 символов.

## Шаг 4. Bootstrap certbot (получение TLS сертификата)

Двухфазный процесс:

### 4.1. Временный http-only nginx

Создайте временный конфиг:

```bash
cat > infra/nginx/admin-bootstrap.conf << 'EOF'
server {
    listen 80;
    server_name ${ADMIN_DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 "Bootstrap mode";
        add_header Content-Type text/plain;
    }
}
EOF
```

Временно замените в `docker-compose.prod.yml`:

```yaml
volumes:
  - ./nginx/admin-bootstrap.conf:/etc/nginx/conf.d/default.conf:ro
```

### 4.2. Запуск и получение сертификата

```bash
make prod.build
PROD_COMPOSE="docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml"
$PROD_COMPOSE up -d nginx certbot
$PROD_COMPOSE run --rm certbot certonly --webroot -w /var/www/certbot -d your-domain.com --email your@email.com --agree-tos --no-eff-email
```

### 4.3. Возврат к полноценному конфигу

Восстановите в `docker-compose.prod.yml`:

```yaml
volumes:
  - ./nginx/admin.conf.template:/etc/nginx/templates/default.conf.template:ro
```

Перезапустите nginx:

```bash
$PROD_COMPOSE up -d nginx
```

## Шаг 5. Первый запуск

```bash
make prod.build
make prod.up
```

Проверьте статус:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml ps
```

## Шаг 6. Настройка offsite backup (TASK-039)

Offsite encrypted backup — критически важен для prod. Следуйте инструкциям:

### 6.1. Генерация age ключевой пары

**ЛОКАЛЬНО** (не на VPS!) сгенерируйте пару ключей:

```bash
age-keygen -o age-backup-key.txt
```

Файл содержит две секции:
- `# public key:` → копируйте в `BACKUP_AGE_RECIPIENT` в `.env`
- `# secret key:` → **НЕ КОММИТЬТЕ**, храните только у себя!

```bash
cat age-backup-key.txt
# Вывод будет примерно таким:
# created: 2026-05-27T12:34:56Z
# public key: age1xyz...abc
# secret key: AGE-SECRET-KEY-1XYZ...
```

**ВАЖНО:** Сохраните `age-backup-key.txt` в надёжном месте (парольный менеджер, encrypted USB). Без этого ключа восстановить бэкап будет **НЕВОЗМОЖНО**.

### 6.2. Настройка rclone

На VPS установите и настройте rclone:

```bash
# Установка (если не установлена)
curl https://rclone.org/install.sh | sudo bash

# Настройка выбранного провайдера (Backblaze B2 показан)
rclone config
# Follow prompts:
# - name: b2 (или s3, gdrive, etc.)
# - type: choose b2 / s3 / etc.
# - account/key: из панели провайдера
# - leave other options default
```

**Рекомендуемые провайдеры** (выбор за владельцем):
- **Backblaze B2** — ~$6/TB/month, простой в настройке
- **AWS S3** — если уже есть AWS аккаунт
- **Google Drive** — rclone "gdrive" type
- **S3-совместимые** — Wasabi, DigitalOcean Spaces, etc.

### 6.3. Настройка `.env`

Добавьте в `infra/.env`:

```bash
# Включить offsite backup
BACKUP_ENABLED=true
# Публичный ключ из age-backup-key.txt (начинается с "age1...")
BACKUP_AGE_RECIPIENT=age1xyz...abc
# rclone remote (соответствует имени из `rclone config`)
BACKUP_RCLONE_REMOTE=b2:bettgbot-prod-backups
# Или для S3: s3:my-bucket/backups
# BACKUP_RCLONE_REMOTE=s3:my-bucket/backups
BACKUP_RETENTION_DAYS=30
```

### 6.4. Первый offsite backup

После настройки перезапустите db-backup сервис:

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml up -d db-backup
```

Запустите первый бэкап вручную:

```bash
make prod.backup.now
```

Проверьте, что файл появился в offsite хранилище:

```bash
# На VPS:
docker exec -it $(docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml ps -q db-backup) sh
rclone lsd b2:bettgbot-prod-backups
# Должна появиться папка с timestamp
```

### 6.5. Weekly verify (GitHub Actions)

Откройте repo Settings → Secrets and variables → Actions, добавьте:

| Secret | Значение |
|--------|----------|
| `VPS_HOST` | IP или hostname VPS |
| `VPS_USER` | SSH user (обычно root или username) |
| `VPS_SSH_KEY` | SSH private key (для подключения к VPS) |
| `REPO_PATH` | Путь к репо на VPS (например `/opt/bettgbot`) |

Workflow `.github/workflows/backup-verify.yml` будет еженедельно (каждое воскресенье в 03:00 UTC) запускать `make prod.backup.verify` через SSH.

### 6.6. Восстановление в DR-сценарии

Если VPS потерян, восстановление на новом сервере:

```bash
# 1. На новом VPS: клонируйте репо, настройте .env (кроме BACKUP_*)
# 2. Скопируйте age-backup-key.txt на новый VPS в ~/.config/age-backup-key.txt
# 3. Восстановите последний бэкап:
make prod.backup.restore.offsite FILE=2026-05-27T02-30-00Z/bettgbot-2026-05-27T02-30-00Z.sql.gz.age AGE_KEY_FILE=~/.config/age-backup-key.txt
```

**ВНИМАНИЕ:** Полный DR-runbook (детальная инструкция по восстановлению после полного отказа VPS) см. в [runbook-dr.md](runbook-dr.md).

## Шаг 7. Первый локальный бэкап

Если offsite backup ещё не настроен, сделайте хотя бы локальный бэкап:

```bash
make prod.backup.now
```

## Шаг 8. Создание первого админа

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml exec web python scripts/create_admin.py --login admin --password "YourSecurePassword" --full-name "Admin"
```

## Шаг 9. Проверка

```bash
make prod.smoke
# или одной командой: автоматически проверит web healthz, статусы сервисов и alembic

# Или вручную:
curl https://your-domain.com/healthz
# Ожидается: 200 OK

make prod.logs
# Ожидается: JSON-строки логов
```

Откройте в браузере `https://your-domain.com/admin` — должен быть логин.

## Шаг 8. Деплой через GitHub Actions (TASK-042)

### Ручной деплой с approval

1. Откройте repo Actions → "Deploy to Production"
2. Нажмите "Run workflow"
3. (Опционально) Укажите конкретный `image_tag` (по умолчанию берётся SHA из main)
4. После прохождения build-images.yml → запрос approval у required reviewers
5. После approval → deploy на VPS + smoke tests
6. При ошибке smoke → автоматический rollback

### Локальный деплой через Makefile

```bash
make prod.deploy IMAGE_TAG=abc1234
```

Для отката:
```bash
make prod.rollback IMAGE_TAG=previous_sha
```

## Регулярные операции

**Просмотр логов:**

```bash
make prod.logs           # все сервисы
docker compose ... logs -f bot   # конкретный сервис
```

**Бэкап БД:**

- Автоматически в 02:30 UTC
- Вручную: `make prod.backup.now`
- Список: `make prod.backup.ls`
- Восстановление: `make prod.backup.restore FILE=bettgbot-YYYY-MM-DDTHH-MM-SSZ.sql.gz`

**Обновление кода:**

```bash
git pull
make prod.build
make prod.up
```

## Откат при проблемах

```bash
git log --oneline
git checkout <stable-sha>
make prod.build
make prod.up
```

Если нужно откатить БД:

```bash
make prod.backup.restore FILE=bettgbot-...
```

## Makefile цели для prod

| Цель | Описание |
|---|---|
| `make prod.build` | Собрать образы |
| `make prod.up` | Поднять стек |
| `make prod.down` | Остановить стек |
| `make prod.logs` | Логи всех сервисов |
| `make prod.ps` | Статус сервисов |
| `make prod.smoke` | Smoke-тесты: web healthz, сервисы, alembic |
| `make prod.backup.now` | Однократный локальный бэкап |
| `make prod.backup.ls` | Список локальных бэкапов |
| `make prod.backup.restore FILE=...` | Восстановить из локального дампа |
| `make prod.backup.verify` | Smoke-restore последнего offsite дампа |
| `make prod.backup.restore.offsite FILE=...` | Восстановить из offsite дампа |
| `make prod.deploy IMAGE_TAG=...` | Деплой с указанным тегом образа |
| `make prod.rollback IMAGE_TAG=...` | Откат к предыдущему тегу образа |

---

## ⚠️ Режим БЕЗ домена (no-domain) — только для закрытых сетей

> **DANGER:** Режим `prod.nodomain.*` использует HTTP без шифрования. П логин/пароль передаются в открытом виде! Используйте ТОЛЬКО в доверительных сетях или через ssh-tunnel.

### Когда использовать no-domain режим

**Единственная рекомендованная причина:** временный доступ к админке на этапе первичной настройки VPS, пока домен ещё не куплен/настроен.

После настройки домена ** ОБЯЗАТЕЛЬНО** перейдите на `prod.*` цели с HTTPS.

### Доступ через ssh-tunnel (рекомендуемый способ)

Вместо прямого HTTP доступа к `http://vps-ip:8888`, используйте ssh-tunnel:

```bash
# На локальной машине:
ssh -L 8888:127.0.0.1:8888 user@vps-ip

# Затем в браузере открывайте:
http://127.0.0.1:8888/admin
```

Это шифрует трафик между вашей машиной и VPS, даже если админка использует HTTP.

### Запуск no-domain режима

```bash
make prod.nodomain.build
make prod.nodomain.up
```

**ВАЖНО:** После запуска порт `8888` доступен только на `127.0.0.1` (localhost внутри VPS), НЕ на `0.0.0.0`. Прямой доступ из интернета закрыт.

### Ограничения no-domain режима

- ❌ Нет HTTPS — пароли передаются в открытом виде (если НЕ использовать ssh-tunnel)
- ❌ Нет HSTS, OCSP stapling, и других защит HTTP/2
- ❌ Браузер может показывать предупреждения о небезопасном сайте
- ❌ Нельзя использовать Service Workers, PWA и другие HTTPS-only API

### Переход на полноценный прод с доменом

Когда домен готов:

1. Следуйте инструкции "Шаг 4. Bootstrap certbot" выше
2. Перейдите на `make prod.up` вместо `make prod.nodomain.up`
3. Убедитесь что `https://your-domain.com/admin` работает
4. (Опционально) Удалите no-domain конфиги: `rm infra/docker-compose.prod-no-domain.yml infra/nginx/admin-no-domain.conf`

## Ссылки

- [02-tech-stack.md](02-tech-stack.md) — стек технологий
- [08-conventions.md](08-conventions.md) — кодовые конвенции
- [runbook-dr.md](runbook-dr.md) — disaster recovery procedures
