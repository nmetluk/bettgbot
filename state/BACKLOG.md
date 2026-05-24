# BACKLOG

Приоритизированная очередь работ. Не таск-трекер построчных тикетов — а каркас того, что нужно сделать до MVP, в логическом порядке.

Когда какой-то пункт идёт в исполнение — он становится `TASK-NNN` в [`handoff/inbox/`](../handoff/inbox/) и помечается здесь как `→ TASK-NNN`.

## Этап 0 — Инфраструктура проекта

- [x] Каркас репозитория, документация, протоколы → завершено сессией `2026-05-22-01`
- [ ] Инициализация git + GitHub-репозиторий + первый коммит → **TASK-001**
- [ ] `pyproject.toml`, выбор пакетного менеджера (uv vs poetry), pre-commit (ruff/mypy) → **TASK-002**
- [ ] CI: GitHub Actions для lint + tests + сборка Docker-образов → **TASK-002 или отдельная**

## Этап 1 — Основания

- [x] `docker-compose.yml` с сервисами postgres + redis для разработки → завершено TASK-003
- [x] Конфиг-слой (pydantic-settings, `.env` → `Settings`-объект) → завершено TASK-004
- [x] ORM-модели: `User`, `Category`, `Event`, `Outcome`, `Prediction`, `ReminderSetting`, `AdminUser`, `AuditLog` (по [`docs/03-data-model.md`](../docs/03-data-model.md)) → завершено TASK-005
- [x] Alembic + первая миграция → завершено TASK-006
- [x] Репозитории (тонкий query-слой, 8 файлов по агрегатам) → завершено TASK-007
- [ ] Интерфейс и mock внешнего API: `ExternalUserRegistryClient` + `MockExternalUserRegistryClient` + `HttpExternalUserRegistryClient` (скелет) → **TASK-008**
- [ ] Сервисы (`UserService`, `EventService`, `PredictionService`, `StatsService`, `ReminderService`, `AuditService`) — композиция репозиториев, транзакции, доменные исключения → **TASK-009**

## Этап 2 — Telegram-бот

- [ ] Скелет aiogram-приложения: bootstrap, диспетчер, middleware, логирование → **TASK-010**
- [ ] `/start` + регистрация через `Contact` + проверка через `ExternalUserRegistryClient` → **TASK-011**
- [ ] Команда «Все события» с пагинацией и фильтром по категории → **TASK-012**
- [ ] Команда «Сделать прогноз» (FSM выбор события → выбор исхода → подтверждение) → **TASK-013**
- [ ] Команда «Мои прогнозы» (активные / архив) → **TASK-014**
- [ ] Команда «Настройка напоминаний» (моменты «за N часов до события», глобальный включить/выключить) → **TASK-015**
- [ ] Команда `/help` → **TASK-016**
- [ ] Фоновая задача (APScheduler/aiogram-scheduler) для рассылки напоминаний → **TASK-017**
- [ ] Фоновая задача архивации событий после фиксации результата → **TASK-018**

## Этап 3 — Веб-админка

- [ ] FastAPI-скелет + Jinja2 + Bootstrap 5 шаблон (выбор: AdminLTE / SB Admin 2 / Volt — решается в задаче) → **TASK-019**
- [ ] Аутентификация админа (логин/пароль, bcrypt, session cookie) → **TASK-020**
- [ ] CRUD категорий → **TASK-021**
- [ ] CRUD событий с привязкой к категории + черновик/опубликовано → **TASK-022**
- [ ] CRUD исходов события → **TASK-023**
- [ ] Фиксация итога события + автоматическая отметка прогнозов как сбылись/нет → **TASK-024**
- [ ] Список пользователей + просмотр их прогнозов и статистики → **TASK-025**
- [ ] Аудит-лог действий в админке → **TASK-026**

## Этап 4 — Подготовка к продакшну

- [ ] Production-ready Docker Compose (override.yml + prod.yml + bot/web сервисы + nginx + healthchecks) → **TASK-027**
- [ ] Бэкап БД (cron, дамп в volume) → **TASK-028**
- [ ] Структурное логирование (JSON, structlog) + ротация → **TASK-029**
- [ ] Readme для деплоя на VPS (пошаговое) → **TASK-030**
- [ ] Smoke-тесты после деплоя → **TASK-031**

## Идеи на будущее (не в MVP)

- Сводная статистика топ-прогнозистов в боте
- Реакции/уведомления при появлении событий в подписанных категориях
- Экспорт прогнозов пользователя в CSV
- Многоязычность (i18n уже заложено архитектурой)

## Технический долг

- **Throttling `UserMiddleware.touch_last_seen`** — сейчас на каждый update идёт SELECT + UPDATE + COMMIT. Под нагрузкой превратить в Redis-кеш «не чаще раза в N минут», flush в БД по таймеру или по cardinality threshold. Триггер — когда метрики покажут реальную нагрузку. Решение зафиксировано в [`state/DECISIONS.md`](DECISIONS.md) (TASK-010 review)
- **`Retry-After` HTTP-date** в `HttpExternalUserRegistryClient` — сейчас парсятся только секунды. HTTP-date добавить, когда контракт реального внешнего API будет согласован и подтверждено, что API может вернуть HTTP-date
- **`AuditLogRepository.list_with_admin`** с `selectinload(admin)` — добавить, когда в админке появится UI аудит-лога (TASK-026), и станет ясно, рендерится ли `entry.admin.full_name`
- **Back-target после FSM «Сделать прогноз», если зашли из «Мои прогнозы»** — после `❌ Отмена` или `✅ Подтвердить` пользователь приземляется в категорию события (через `PredictStartCb.back_category_id = event.category_id`), а не обратно в «Мои прогнозы». Решение: либо расширить три prediction-CB полем `back_my_tab: MyTab \| None`, либо хранить back в FSM-data с сериализацией. Триггер фикса — сигнал из UX-наблюдений (TASK-014 review)
- **`PredictionRepository.list_*_by_user_with_relations`** с `selectinload(Event, Event.outcomes)` — сейчас в `_build_my_view` (TASK-014) идёт N+1 (до 7 SELECT'ов на страницу для подгрузки события и исходов). Триггер — горячая точка под реальной нагрузкой
- **Cleanup старых `reminder_dispatch_log`** — таблица растёт линейно с активностью (минимум 1 запись на каждое отправленное напоминание). Через год оценим объём и реализуем TTL-job (например, удалять записи старше 90 дней) либо партиции по `dispatched_at`. Триггер — реальный объём БД (TASK-017)
- **Index `ix_reminder_dispatch_log_dispatched_at`** — нужен для будущего cleanup-job по TTL. На MVP без него, потому что `dispatched_at` не используется в запросах. Триггер — реализация cleanup (TASK-017)
- **`fresh_db`-фикстура должна делать `TRUNCATE ... CASCADE` перед `downgrade base`** — текущая фикстура хрупкая: если тест оставит «архивный без result» после миграции 0003 (или похожие нарушения новых инвариантов в будущих миграциях), следующая test session не сможет `downgrade base`, потому что старый CHECK ругнётся на наследие. Сейчас обход через TRUNCATE в самом тесте (`test_0003_relax_event_archive_check`); жёсткая изоляция нужна, когда появится второй похожий тест. Триггер — `pytest`-флак из-за межтестовой грязи (TASK-018 review)
- **Скомпилировать `volt.css` из SCSS-источников Volt Free** для фирменного стайлинга админки — сейчас в `src/admin/static/css/volt.css` placeholder, Bootstrap 5 CDN покрывает базовую вёрстку. Команды: `git clone https://github.com/themesberg/volt-bootstrap-5-dashboard.git && cd volt && npm install && npm run build && cp dist/assets/css/volt.css <project>/src/admin/static/css/`. Триггер — реальная UX-нужда в TASK-021+ с custom-styled элементами (TASK-019 review)
- **Переход с `fastapi-limiter 0.1.6` на 0.2+** — в 0.2 переписан API на `pyrate-limiter` (`Limiter` вместо `FastAPILimiter`, новые `Depends`). Требует переписать lifespan и `Depends(RateLimiter(times=, seconds=))` в `routes/login.py`. Триггер — security advisory против 0.1.6 или нужда в новых фичах (TASK-020 review)
