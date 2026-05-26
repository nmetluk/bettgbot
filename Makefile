# Makefile для повседневной работы с dev-инфрой Betting Bot.
# Запускается из корня репо; compose-файл живёт в infra/.
# Переменные окружения берутся из .env (рядом с Makefile, в репо не коммитится).
#
# Целевая аудитория — разработчик на macOS / Linux. POSIX-совместимые конструкции, без bash-измов.

# Базовый COMPOSE — base + dev-override. Явное указание `-f override.yml` нужно
# потому что compose v2 не делает auto-merge override-файла рядом с base, если
# base указан явным `-f path/to/...`. Без override `make up` поднимет и bot+web
# из base, потеряв `profiles: [full]`, который живёт только в override.
COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.override.yml
PROD_COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod.yml
PROD_NO_DOMAIN_COMPOSE := docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml

.PHONY: help up down restart logs ps db.psql redis.cli nuke \
        migrate rollback rollback.all migration.new migration.current migration.history \
        admin admin.create admin.create.prod full.up \
        prod.build prod.up prod.down prod.logs prod.ps prod.shell.bot prod.shell.web \
        prod.certbot.init prod.backup.now prod.backup.ls prod.backup.restore prod.smoke \
        prod.nodomain.build prod.nodomain.up prod.nodomain.down prod.nodomain.logs prod.nodomain.ps

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

prod.backup.now: ## Однократный pg_dump прямо сейчас
	@$(PROD_COMPOSE) run --rm db-backup sh -c 'pg_dump -h db -U $$POSTGRES_USER $$POSTGRES_DB --no-owner --clean --if-exists | gzip > /backups/bettgbot-$$(date -u +%FT%H-%M-%SZ).sql.gz'

prod.backup.ls: ## Список бэкапов в volume
	@$(PROD_COMPOSE) exec db-backup ls -lah /backups

prod.backup.restore: ## Восстановить дамп: make prod.backup.restore FILE=bettgbot-2026-05-25T02-30-00Z.sql.gz
	@if [ -z "$(FILE)" ]; then \
		echo "Использование: make prod.backup.restore FILE=bettgbot-YYYY-MM-DDTHH-MM-SSZ.sql.gz"; \
		exit 1; \
	fi
	@printf "ВСЕ ТЕКУЩИЕ ДАННЫЕ В БД БУДУТ ЗАМЕНЕНЫ дампом '$(FILE)'. Введите 'RESTORE' для подтверждения: "; \
	read ans; \
	if [ "$$ans" = "RESTORE" ]; then \
		$(PROD_COMPOSE) exec -T db-backup sh -c 'gunzip -c /backups/$(FILE)' | $(PROD_COMPOSE) exec -T db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'; \
		echo "✓ Restore завершён"; \
	else \
		echo "Отмена."; \
		exit 1; \
	fi

prod.certbot.init: ## Получить первый TLS сертификат (bootstrap mode)
	@echo "Убедись что DNS-запись $$ADMIN_DOMAIN → IP VPS уже распространена."
	@echo "Временно использует admin-bootstrap.conf (http-only)."
	# --entrypoint="" обязательно: сервис certbot в prod.yml имеет entrypoint
	# с бесконечным renew-loop. Без override команда certonly уйдёт как args
	# к sh, а не к certbot, и первый сертификат не выпустится.
	$(PROD_COMPOSE) run --rm --entrypoint="" certbot certbot certonly --webroot -w /var/www/certbot -d $$ADMIN_DOMAIN --email $$TLS_EMAIL --agree-tos --no-eff-email

admin.create.prod: ## Создать админа в prod: make admin.create.prod LOGIN=admin PASSWORD="..."
		@if [ -z "$(LOGIN)" ] || [ -z "$(PASSWORD)" ]; then \
			echo "Использование: make admin.create.prod LOGIN=admin PASSWORD=\"...\" [FULL_NAME=\"...\"]"; \
			exit 1; \
		fi
		$(PROD_COMPOSE) exec -T web python scripts/create_admin.py \
			--login "$(LOGIN)" --password "$(PASSWORD)" \
			$(if $(FULL_NAME),--full-name "$(FULL_NAME)")

prod.smoke: ## Smoke-тесты после деплоя: web healthz, services, alembic
	@./scripts/smoke_test.sh

# ==== Prod БЕЗ домена (порт 8888, без TLS) ====

prod.nodomain.build: ## Собрать prod-образы для no-domain (порт 8888)
	$(PROD_NO_DOMAIN_COMPOSE) build

prod.nodomain.up: ## Поднять prod-stack без домена (порт 8888)
	$(PROD_NO_DOMAIN_COMPOSE) up -d
	$(PROD_NO_DOMAIN_COMPOSE) ps

prod.nodomain.down: ## Остановить prod-stack без домена
	$(PROD_NO_DOMAIN_COMPOSE) down

prod.nodomain.logs: ## Tail логов no-domain prod
	$(PROD_NO_DOMAIN_COMPOSE) logs -f --tail=100

prod.nodomain.ps: ## Статус no-domain prod сервисов
	$(PROD_NO_DOMAIN_COMPOSE) ps
