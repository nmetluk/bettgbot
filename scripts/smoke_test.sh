#!/usr/bin/env bash
# smoke_test.sh — проверки живучести после деплоя.
# Запускается через make prod.smoke (или вручную).
#
# Переменная BB_COMPOSE_ARGS позволяет переопределить compose-файлы
# для dev-окружения (CI): BB_COMPOSE_ARGS='-f infra/docker-compose.yml -f infra/docker-compose.override.yml'

set -euo pipefail

# Compose по умолчанию — prod, можно переопределить через BB_COMPOSE_ARGS
COMPOSE="docker compose ${BB_COMPOSE_ARGS:---f infra/docker-compose.yml -f infra/docker-compose.prod.yml}"

echo "→ Checking web /healthz..."
for i in $(seq 1 12); do
    if curl -sf http://127.0.0.1:8000/healthz > /dev/null 2>&1; then
        echo "  ✓ web /healthz OK"
        break
    fi
    if [ "$i" -eq 12 ]; then
        echo "  ✗ web /healthz не отвечает за 60s"
        exit 1
    fi
    sleep 5
done

echo "→ Checking docker compose services..."
# Проверяем что критичные сервисы живы (running или healthy)
# Парсим вывод compose ps — ищем "exited", "dead" среди критичных сервисов
services_output=$($COMPOSE ps --format json 2>/dev/null || echo "[]")

check_service() {
    local name=$1
    #jq -r ".[] | select(.Name==\"$name\") | .State" <<< "$services_output"
    # Используем grep как fallback, если jq не установлен
    state=$(echo "$services_output" | grep -o "\"Name\":\"$name\"[^}]*\"State\":\"[^\"]*\"" | grep -o "\"State\":\"[^\"]*\"" | cut -d'"' -f4)

    case "$state" in
        running|healthy)
            echo "    ✓ $name: $state"
            return 0
            ;;
        *)
            echo "    ✗ $name: $state (expected running/healthy)"
            return 1
            ;;
    esac
}

# Проверяем критичные сервисы
all_ok=true
check_service "bot" || all_ok=false
check_service "web" || all_ok=false
check_service "db" || all_ok=false
check_service "nginx" || all_ok=false
check_service "db-backup" || all_ok=false

if [ "$all_ok" = true ]; then
    echo "  ✓ docker compose services OK"
else
    echo "  ✗ some services are not healthy"
    exit 1
fi

echo "→ Checking alembic version..."
current=$($COMPOSE exec -T web alembic current 2>/dev/null | grep -oE '^[a-f0-9]+')
head=$($COMPOSE exec -T web alembic heads 2>/dev/null | grep -oE '^[a-f0-9]+')
if [ -z "$current" ] || [ -z "$head" ]; then
    echo "  ✗ alembic check failed (current=$current, head=$head)"
    exit 1
fi
if [ "$current" = "$head" ]; then
    echo "  ✓ alembic sync OK (current=$current)"
else
    echo "  ✗ alembic out of sync: current=$current, head=$head"
    exit 1
fi

echo ""
echo "✓ Smoke tests passed"
