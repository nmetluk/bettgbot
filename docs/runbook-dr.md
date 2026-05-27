# Disaster Recovery Runbook

Документ описывает пошаговые процедуры по восстановлению сервиса после критических инцидентов.

## Целевые метрики

| Метрика | Цель | Описание |
|---------|------|----------|
| **RTO** (Recovery Time Objective) | ≤8 часов | Максимальное время простоя после полного отказа VPS |
| **RPO** (Recovery Point Objective) | ≤24 часа | Максимально возможная потеря данных (зависит от частоты offsite backup) |

## Критичная информация владельца

| Ресурс | Расположение | Описание |
|--------|-------------|----------|
| SSH ключ к VPS | Локальный keychain | Для доступа к серверу |
| Age private ключ | Локальный keychain | Для расшифровки бэкапов БД (НЕ хранить на VPS!) |
| Домен | Регистратор | DNS A-запись → IP VPS |
| `.env` | На VPS (`/opt/bettgbot/infra/.env`) | Содержит секреты (BACKUP, TOKENS) |
| Offsite backup | rclone remote (B2/S3/etc) | Шифрованные дампы БД |

---

## Сценарий 1: VPS физически потерян

**Симптомы:** VPS недоступен, провайдер подтвердает потерю данных/сервера.

### Шаг 1: Заказать новый VPS

Требования:
- **ОС:** Ubuntu 24.04 LTS
- **Ресурсы:** ≥2 GB RAM, ≥40 GB SSD
- **Доступ:** SSH по ключу

### Шаг 2: Установить Docker + Compose plugin

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2-plugin git make
sudo systemctl enable docker
sudo systemctl start docker
```

### Шаг 3: Клонировать репозиторий

```bash
sudo mkdir -p /opt/bettgbot
sudo chown $USER:$USER /opt/bettgbot
git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot
cd /opt/bettgbot
```

### Шаг 4: Восстановить `.env`

**ВАЖНО:** `.env` не коммитится. Восстановите из:
- Локальной копии (если сохраняли)
- Парольного менеджера владельца
- SOPS/GitOps (если настроено)

Минимальный набор для восстановления:
```bash
cp infra/.env.prod.example infra/.env
nano infra/.env  # Заполните ОБЯЗАТЕЛЬНЫЕ поля
```

### Шаг 5: Установить rclone + age, восстановить ключи

```bash
# Установка rclone
curl https://rclone.org/install.sh | sudo bash

# Установка age
curl -sSf https://raw.githubusercontent.com/FiloSottile/age/main/install.sh | sh

# Восстановить age private ключ из keychain владельца
mkdir -p ~/.config
# Скопировать содержимое age-backup-key.txt в ~/.config/age-backup-key.txt
chmod 600 ~/.config/age-backup-key.txt
```

Настроить rclone (заново):
```bash
rclone config
# Используйте те же credentials, что были на оригинальном VPS
```

### Шаг 6: Найти последний offsite backup

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml run --rm db-backup sh -c "rclone lsd $BACKUP_RCLONE_REMOTE | tail -1"
# Или:
make prod.backup.ls
```

### Шаг 7: Восстановить БД из offsite backup

```bash
# Замените TIMESTAMP на реальное значение из шага 6
make prod.backup.restore.offsite FILE=TIMESTAMP/bettgbot-TIMESTAMP.sql.gz.age AGE_KEY_FILE=~/.config/age-backup-key.txt
```

### Шаг 8: Поднять сервисы

```bash
make prod.up
make prod.smoke
```

### Шаг 9: Обновить DNS

В панели регистратора домена обновите A-запись:
```
your-domain.com A <NEW_VPS_IP>
```

Проверьте распространение:
```bash
nslookup your-domain.com
```

### Шаг 10: Получить TLS сертификат (если новый домен)

```bash
make prod.certbot.init
```

### Проверка

```bash
curl https://your-domain.com/healthz
# Ожидается: 200 OK
```

---

## Сценарий 2: БД повреждена (например, неудачная миграция)

**Симптомы:** Бот/Web выдают ошибки БД, миграции не накатываются.

### Шаг 1: Остановить writers

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml stop bot web
```

### Шаг 2: Восстановить из локального backup

```bash
make prod.backup.ls  # Найти нужный дамп
make prod.backup.restore FILE=bettgbot-YYYY-MM-DDTHH-MM-SSZ.sql.gz
```

### Шаг 3: Проверить миграцию

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml exec -T db-backup alembic current
```

### Шаг 4: Поднять сервисы

```bash
make prod.up
make prod.smoke
```

---

## Сценарий 3: Откат деплоя (плохая версия)

**Симптомы:** После деплоя smoke tests падают, ошибки в логах.

### Быстрый откат через Makefile

```bash
# Найти предыдущий SHA
git log --oneline -5

# Откатить
make prod.rollback IMAGE_TAG=previous_abc1234
```

### Откат через GitHub Actions

1. Откройте Actions → Deploy to Production
2. Нажмите "Run workflow"
3. Введите `image_tag` предыдущей версии
4. Запустите workflow (требуется approval)

---

## Профилактика

### Регулярное тестирование DR-процедуры

Рекомендуется раз в квартал проводить DR-тренировку:
1. Подъём staging-окружения с нуля
2. Восстановление БД из offsite backup
3. Проверка smoke tests

### Мониторинг

- **Healthchecks.io** — пинг uptime (настроен в `docs/07-deployment.md`)
- **Sentry** — мониторинг ошибок (настроен в `TASK-041`)
- **Weekly backup verify** — GitHub Actions workflow (`.github/workflows/backup-verify.yml`)

### Contact-info владельца

Для оперативной связи в случае инцидента:
- Telegram: (заполнить владельцем)
- Email: (заполнить владельцем)
- Phone: (заполнить владельцем)

---

## Ссылки

- [07-deployment.md](07-deployment.md) — Основной деплой
- [03-data-model.md](03-data-model.md) — Структура БД
- TASK-039 — Offsite encrypted backup
- TASK-042 — Image tagging + deploy workflow
