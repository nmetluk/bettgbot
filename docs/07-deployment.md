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

## Шаг 6. Первый бэкап

Важно: cron делает бэкап раз в сутки, первый — через 24 часа. Сделайте вручную сейчас:

```bash
make prod.backup.now
```

## Шаг 7. Создание первого админа

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml exec web python scripts/create_admin.py --login admin --password "YourSecurePassword" --full-name "Admin"
```

## Шаг 8. Проверка

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
| `make prod.backup.now` | Однократный бэкап |
| `make prod.backup.ls` | Список бэкапов |
| `make prod.backup.restore FILE=...` | Восстановить из дампа |

## Ссылки

- [02-tech-stack.md](02-tech-stack.md) — стек технологий
- [08-conventions.md](08-conventions.md) — кодовые конвенции
