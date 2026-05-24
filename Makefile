# Makefile для повседневной работы с dev-инфрой Betting Bot.
# Запускается из корня репо; compose-файл живёт в infra/.
# Переменные окружения берутся из .env (рядом с Makefile, в репо не коммитится).
#
# Целевая аудитория — разработчик на macOS / Linux. POSIX-совместимые конструкции, без bash-измов.

COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml
PROD_COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml

.PHONY: help up down restart logs ps db.psql redis.cli nuke \
        migrate rollback rollback.all migration.new migration.current migration.history \
        admin admin.create full.up backup \
        prod.build prod.up prod.down prod.logs prod.ps prod.shell.bot prod.shell.web

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

migrate: ## Применить все миграции (alembic upgrade head)
	uv run alembic upgrade head

rollback: ## Откатить одну миграцию (alembic downgrade -1)
	uv run alembic downgrade -1

rollback.all: ## ОПАСНО: откатить ВСЕ миграции (alembic downgrade base) — БД пустеет
	@printf "ВСЕ ТАБЛИЦЫ ПРИЛОЖЕНИЯ БУДУТ УДАЛЕНЫ. Введите 'ROLLBACK' для подтверждения: "; \
	read ans; \
	if [ "$$ans" = "ROLLBACK" ]; then \
		uv run alembic downgrade base; \
	else \
		echo "Отмена."; \
		exit 1; \
	fi

migration.new: ## Сгенерировать новую миграцию: make migration.new MSG="add foo"
	@if [ -z "$(MSG)" ]; then \
		echo "Использование: make migration.new MSG=\"описание\""; \
		exit 1; \
	fi
	uv run alembic revision --autogenerate -m "$(MSG)"

migration.current: ## Показать текущую ревизию alembic_version
	uv run alembic current

migration.history: ## История миграций (alembic history --verbose)
	uv run alembic history --verbose

admin: ## Запустить веб-админку через uvicorn (auto-reload)
	uv run uvicorn src.admin.app:app --reload --host 127.0.0.1 --port 8000

admin.create: ## Создать админа: make admin.create LOGIN=admin PASSWORD="..." [FULL_NAME="..."]
	@if [ -z "$(LOGIN)" ] || [ -z "$(PASSWORD)" ]; then \
		echo "Использование: make admin.create LOGIN=admin PASSWORD=\"...\" [FULL_NAME=\"...\"]"; \
		exit 1; \
	fi
	PYTHONPATH=. uv run python scripts/create_admin.py \
		--login "$(LOGIN)" --password "$(PASSWORD)" \
		$(if $(FULL_NAME),--full-name "$(FULL_NAME)")

full.up: ## Поднять полный dev-stack (db + redis + bot + web в контейнерах)
	$(COMPOSE) --profile full up -d

prod.build: ## Собрать prod-образы bot+web
	$(PROD_COMPOSE) build

prod.up: ## Поднять prod-stack (с nginx)
	$(PROD_COMPOSE) up -d
	$(PROD_COMPOSE) ps

prod.down: ## Остановить prod-stack
	$(PROD_COMPOSE) down

prod.logs: ## Tail prod-логов всех сервисов
	$(PROD_COMPOSE) logs -f --tail=100

prod.ps: ## Статус prod-сервисов
	$(PROD_COMPOSE) ps

prod.shell.bot: ## Открыть shell в prod bot-контейнере
	$(PROD_COMPOSE) exec bot sh

prod.shell.web: ## Открыть shell в prod web-контейнере
	$(PROD_COMPOSE) exec web sh

backup: ## Зеркалирование handoff/state/sessions в локально-синкнутую Drive-папку (после git pull main)
	@./scripts/backup-to-drive.sh
