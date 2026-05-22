# Makefile для повседневной работы с dev-инфрой Betting Bot.
# Запускается из корня репо; compose-файл живёт в infra/.
# Переменные окружения берутся из .env (рядом с Makefile, в репо не коммитится).
#
# Целевая аудитория — разработчик на macOS / Linux. POSIX-совместимые конструкции, без bash-измов.

COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml

.PHONY: help up down restart logs ps db.psql redis.cli nuke

help: ## Показать доступные команды
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_.-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Поднять postgres + redis в фоне
	$(COMPOSE) up -d

down: ## Остановить сервисы (volume'ы остаются)
	$(COMPOSE) down

restart: ## Перезапустить сервисы
	$(COMPOSE) restart

logs: ## Tail логов всех сервисов
	$(COMPOSE) logs -f

ps: ## Статус сервисов (включая healthcheck)
	$(COMPOSE) ps

db.psql: ## Открыть psql в контейнере db
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"'

redis.cli: ## Открыть redis-cli в контейнере redis
	$(COMPOSE) exec redis redis-cli

nuke: ## ОПАСНО: down -v — стирает volume'ы pg_data и redis_data
	@printf "ВСЕ ДАННЫЕ В pg_data И redis_data БУДУТ УДАЛЕНЫ. Введите 'NUKE' для подтверждения: "; \
	read ans; \
	if [ "$$ans" = "NUKE" ]; then \
		$(COMPOSE) down -v; \
	else \
		echo "Отмена."; \
		exit 1; \
	fi
