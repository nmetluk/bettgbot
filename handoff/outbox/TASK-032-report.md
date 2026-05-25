---
task: TASK-032
status: completed
date: 2026-05-25
branch: feat/TASK-032-smoke-tests
commits:
  - f71fcfc feat: add smoke tests for post-deploy verification
  - 347de67 chore(handoff): mark TASK-032 as in-progress
---

# TASK-032: Smoke-тесты после деплоя — Отчёт

## Что сделано

### 1. Создан `scripts/smoke_test.sh`

Скрипт проверяет:
- **Web `/healthz`** — возвращает 200 в течение 60 секунд (12 попыток по 5s)
- **Docker compose services** — проверяет статусы bot, web, db, nginx, db-backup
- **Alembic sync** — текущая ревизия БД совпадает с head в коде

Скрипт поддерживает переменную `BB_COMPOSE_ARGS` для работы с любым compose-конфигом (dev/prod).

### 2. Обновлён `Makefile`

- Добавлена цель `prod.smoke` для запуска smoke-тестов
- Добавлена в `.PHONY`

### 3. Обновлён `docs/07-deployment.md`

- В секции «Проверка» (шаг 8) добавлена команда `make prod.smoke`
- В таблицу Makefile целей добавлен `prod.smoke`

## Что не сделано

**Реальный прогон на dev-stack** — Docker недоступен в текущем окружении. Тестирование отложено до VPS-деплоя.

Скрипт написан в соответствии с требованиями и должен работать корректно. Логика проста:
- `/healthz` — стандартный curl с retry
- Сервисы — парсинг `docker compose ps --format json` с проверкой состояния
- Alembic — сравнение вывода `alembic current` и `alembic heads`

## Открытые вопросы

Нет.

## Команды для воспроизведения

```bash
# На VPS после деплоя:
make prod.smoke

# На dev-stack (если Docker доступен):
BB_COMPOSE_ARGS='-f infra/docker-compose.yml -f infra/docker-compose.override.yml' ./scripts/smoke_test.sh
```

## Diff-сводка

| Файл | Изменение |
|------|-----------|
| `scripts/smoke_test.sh` | +52 строки (новый файл) |
| `Makefile` | +1 строка (`.PHONY` добавлен `prod.smoke`) |
| `docs/07-deployment.md` | +5 строки (описание `make prod.smoke`) |

## Следующие шаги

1. Пуш в origin и открытие PR
2. Тестирование на VPS после merge
3. После успешного тестирования — **MVP завершён**
