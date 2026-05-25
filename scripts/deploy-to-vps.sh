#!/bin/bash
# Скрипт деплоя Betting Bot на VPS без домена (по IP, порт 8888).
# Использование: ./scripts/deploy-to-vps.sh <vps-ip> [ssh-user]
# По умолчанию ssh-user = root

set -e

VPS_IP="${1:-}"
SSH_USER="${2:-root}"

if [ -z "$VPS_IP" ]; then
    echo "Использование: $0 <vps-ip> [ssh-user]"
    echo "Пример: $0 5.188.88.78 root"
    exit 1
fi

echo "=========================================="
echo " Деплой Betting Bot на VPS"
echo " IP: $VPS_IP"
echo " SSH: $SSH_USER"
echo " Порт: 8888 (без TLS)"
echo "=========================================="
echo ""

# Проверка локальных файлов
echo "→ Проверка локальных файлов..."
if [ ! -f "infra/.env" ]; then
    echo "❌ ОШИБКА: infra/.env не найден!"
    echo "   Создай его: cp infra/.env.example infra/.env"
    echo "   И заполните ОБЯЗАТЕЛЬНЫЕ поля:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - POSTGRES_PASSWORD"
    echo "   - ADMIN_SECRET_KEY"
    echo "   - ADMIN_CSRF_SECRET"
    exit 1
fi

# Проверка заполненных обязательных переменных
source infra/.env
REQUIRED_VARS=("TELEGRAM_BOT_TOKEN" "POSTGRES_PASSWORD" "ADMIN_SECRET_KEY" "ADMIN_CSRF_SECRET")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ] || [[ "${!var}" == *"change-me"* ]]; then
        echo "❌ ОШИБКА: $var не заполнен в infra/.env"
        exit 1
    fi
done

echo "✓ Локальные файлы в порядке"
echo ""

# Функция для выполнения команд на VPS
ssh_exec() {
    ssh -o StrictHostKeyChecking=no "$SSH_USER@$VPS_IP" "$1"
}

# Функция для копирования файлов на VPS
scp_to_vps() {
    scp -o StrictHostKeyChecking=no "$1" "$SSH_USER@$VPS_IP:$2"
}

# Шаг 1: Установка зависимостей на VPS
echo "→ Шаг 1: Установка Docker на VPS..."
ssh_exec "
set -e
if ! command -v docker &> /dev/null; then
    sudo apt update
    sudo apt install -y docker.io docker-compose-v2-plugin git make
    sudo systemctl enable docker
    sudo systemctl start docker
    echo '✓ Docker установлен'
else
    echo '✓ Docker уже установлен'
fi
docker --version
docker compose version
"

# Шаг 2: Клонирование репо
echo ""
echo "→ Шаг 2: Клонирование репозитория..."
ssh_exec "
set -e
if [ -d /opt/bettgbot ]; then
    echo '→ Репо уже существует, обновляем...'
    cd /opt/bettgbot
    git fetch origin
    git reset --hard origin/main
    git pull origin main
else
    sudo mkdir -p /opt/bettgbot
    sudo chown \$USER:\$USER /opt/bettgbot
    git clone https://github.com/nmetluk/bettgbot.git /opt/bettgbot
fi
cd /opt/bettgbot
echo '✓ Репо готово'
git log --oneline -1
"

# Шаг 3: Копирование .env на VPS
echo ""
echo "→ Шаг 3: Настройка .env на VPS..."
scp_to_vps "infra/.env" "/opt/bettgbot/infra/.env"
echo "✓ .env скопирован"

# Шаг 4: Сборка образов
echo ""
echo "→ Шаг 4: Сборка Docker-образов на VPS..."
ssh_exec "
set -e
cd /opt/bettgbot
make prod.nodomain.build
"

# Шаг 5: Запуск сервисов
echo ""
echo "→ Шаг 5: Запуск сервисов..."
ssh_exec "
set -e
cd /opt/bettgbot
make prod.nodomain.up
sleep 5
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml ps
"

# Шаг 6: Проверка
echo ""
echo "→ Шаг 6: Проверка здоровья сервисов..."
ssh_exec "
set -e
cd /opt/bettgbot
sleep 3
curl -s http://127.0.0.1:8888/healthz && echo ' ✓ Healthz OK' || echo ' ❌ Healthz failed'
"

echo ""
echo "=========================================="
echo "✓ Деплой завершён!"
echo "=========================================="
echo ""
echo "Доступные URLs:"
echo "  Админка:  http://$VPS_IP:8888/admin"
echo "  Healthz:  http://$VPS_IP:8888/healthz"
echo ""
echo "Следующие шаги:"
echo "  1. Создай админа на VPS:"
echo "     ssh $SSH_USER@$VPS_IP"
echo "     cd /opt/bettgbot"
echo "     docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml exec web python scripts/create_admin.py --login admin --password 'ВашПароль'"
echo ""
echo "  2. Проверь логи:"
echo "     ssh $SSH_USER@$VPS_IP 'cd /opt/bettgbot && make prod.nodomain.logs'"
echo ""
echo "  3. Первый бэкап:"
echo "     ssh $SSH_USER@$VPS_IP 'cd /opt/bettgbot && make prod.backup.now'"
echo ""
