# 01 — Архитектура

Документ описывает высокоуровневое разбиение системы на компоненты, их обязанности и протоколы взаимодействия. Технологии — в [02-tech-stack.md](02-tech-stack.md), модель данных — в [03-data-model.md](03-data-model.md).

## Контекстная диаграмма

```mermaid
flowchart LR
    user([Пользователь Telegram])
    admin([Администратор])
    ext[(Внешний реестр пользователей<br/>HTTP API)]

    subgraph Betting Bot System
        bot[Bot Service<br/>aiogram]
        web[Admin Web<br/>FastAPI + Jinja2]
        db[(PostgreSQL)]
        redis[(Redis<br/>FSM + cache)]
    end

    user -- Telegram MTProto --> bot
    admin -- HTTPS --> web
    bot -- HTTPS --> ext
    bot <--> db
    bot <--> redis
    web <--> db
```

Внутри системы — два запускаемых процесса (`bot` и `web`), две хранилища (Postgres, Redis), один внешний интегратор (реестр пользователей).

## Компоненты

### Bot Service (`src/bot/`)

Telegram-бот на aiogram 3. Отвечает за весь пользовательский UX:

- Регистрация через `Contact`, проверка в реестре, создание `User` в БД.
- Меню и команды: все события, сделать прогноз, мои прогнозы, напоминания, /help.
- FSM-состояния для многошаговых сценариев (Redis-storage).
- Фоновые задачи: рассылка напоминаний, архивация прошедших событий после фиксации итога.

**Не отвечает** за бизнес-операции напрямую — вызывает сервисы из `src/shared/services/`.

### Admin Web (`src/admin/`)

FastAPI + Jinja2 + HTMX + Bootstrap 5. Серверный рендеринг — никакого SPA. Отвечает за:

- Аутентификацию админа (логин/пароль, session cookie).
- CRUD категорий, событий, исходов.
- Фиксацию итога события (триггерит автоматическую отметку всех связанных прогнозов как сбылись/не сбылись).
- Просмотр пользователей и их прогнозов.
- Аудит-лог.

Тоже использует сервисы из `src/shared/services/`, чтобы бизнес-логика не дублировалась.

### Shared (`src/shared/`)

Сердце системы. Здесь:

- **`models/`** — SQLAlchemy 2.0 модели (User, Category, Event, Outcome, Prediction, ReminderSetting, AdminUser, AuditLog).
- **`db.py`** — фабрика сессий, асинхронный engine.
- **`repositories/`** — тонкий слой запросов к БД (один репозиторий на агрегат).
- **`services/`** — бизнес-логика: `UserService` (регистрация, проверка), `EventService` (создание/архивация), `PredictionService` (приём/отметка), `StatsService`, `ReminderService`.
- **`external/`** — клиент внешнего реестра (`ExternalUserRegistryClient` интерфейс + `HttpExternalUserRegistryClient` + `MockExternalUserRegistryClient`).
- **`config.py`** — pydantic-settings.
- **`logging.py`** — настройка structlog.

Принципиальное правило: бот и админка **не лезут** в БД напрямую — только через сервисы. Это обеспечивает единую бизнес-логику и тестируемость.

### Migrations (`src/migrations/`)

Alembic. Применяются при старте контейнера `bot` или `web` (или отдельной командой в CI/CD).

### Infra (`infra/`)

Docker Compose, Dockerfile-ы, `.env.example`. Подробно — [07-deployment.md](07-deployment.md).

## Слои внутри сервисов

```
┌─────────────────────────────────────────────┐
│  Handlers / Routes (bot/handlers, admin/routes)
│  ──────────────────────────────────────────
│  • Парсинг входящего (Telegram update / HTTP request)
│  • Валидация параметров
│  • Вызов сервиса
│  • Форматирование ответа (Telegram message / HTML template)
├─────────────────────────────────────────────┤
│  Services (shared/services)
│  ──────────────────────────────────────────
│  • Бизнес-правила и инварианты
│  • Композиция вызовов репозиториев
│  • Транзакции
│  • Вызов внешних адаптеров
├─────────────────────────────────────────────┤
│  Repositories (shared/repositories)
│  ──────────────────────────────────────────
│  • CRUD-операции по агрегату
│  • Сложные запросы под конкретный сервис
├─────────────────────────────────────────────┤
│  Models + DB (shared/models, shared/db)
│  ──────────────────────────────────────────
│  • SQLAlchemy mappings
│  • Engine, AsyncSession
└─────────────────────────────────────────────┘
```

## Поток данных: «Пользователь делает прогноз»

```mermaid
sequenceDiagram
    autonumber
    participant U as Пользователь
    participant TG as Telegram
    participant H as Bot Handler
    participant S as PredictionService
    participant R as Repositories
    participant DB as PostgreSQL

    U->>TG: Жмёт «Сделать прогноз» → выбор события → выбор исхода
    TG->>H: Update (callback_query)
    H->>S: make_prediction(user_id, event_id, outcome_id)
    S->>R: event.get(event_id) + проверки (не архив, не прошёл дедлайн)
    R->>DB: SELECT
    S->>R: prediction.upsert(user, event, outcome)
    R->>DB: INSERT/UPDATE в транзакции
    S-->>H: Prediction (или ошибка домена)
    H-->>TG: Ответ «прогноз принят / ошибка»
    TG-->>U: Сообщение
```

## Поток данных: «Админ фиксирует итог события»

```mermaid
sequenceDiagram
    autonumber
    participant A as Админ
    participant W as Admin Web
    participant ES as EventService
    participant PS as PredictionService
    participant DB as PostgreSQL

    A->>W: POST /events/{id}/result   (форма с выбранным Outcome)
    W->>ES: set_result(event_id, outcome_id, admin_id)
    ES->>DB: BEGIN
    ES->>DB: UPDATE event SET result_outcome_id=…, is_archived=true, archived_at=now()
    ES->>PS: mark_predictions(event_id, outcome_id)
    PS->>DB: UPDATE prediction SET is_correct = (outcome_id = $1) WHERE event_id = $2
    ES->>DB: INSERT INTO audit_log(...)
    ES->>DB: COMMIT
    ES-->>W: ok
    W-->>A: редирект на страницу события с зелёным баннером
```

## Поток данных: «Регистрация пользователя»

```mermaid
sequenceDiagram
    autonumber
    participant U as Пользователь
    participant TG as Telegram
    participant H as Bot Handler /start
    participant US as UserService
    participant EX as ExternalRegistry (mock/http)
    participant DB as PostgreSQL

    U->>TG: /start
    TG->>H: Update
    H-->>TG: Сообщение «нажмите кнопку, чтобы поделиться контактом» + ReplyKeyboard с request_contact
    U->>TG: Нажимает кнопку → отправляет контакт
    TG->>H: Update с Contact
    H->>US: register_or_authenticate(tg_user_id, phone)
    US->>DB: SELECT user WHERE tg_user_id = ?
    alt уже есть
        US-->>H: User (existing)
    else нет — пробуем создать
        US->>EX: verify(phone)
        alt подтверждён
            US->>DB: INSERT user
            US-->>H: User (new)
        else нет в реестре
            US-->>H: NotAllowedError
        end
    end
    H-->>TG: Главное меню / сообщение об ошибке
```

## Развёртывание (топология)

```mermaid
flowchart TB
    subgraph VPS
        nginx[nginx<br/>reverse proxy + TLS]
        subgraph compose [docker-compose]
            bot_c[bot container]
            web_c[web container]
            pg_c[(postgres container<br/>volume)]
            redis_c[(redis container)]
        end
        nginx --> web_c
    end

    tg_servers((Telegram Bot API))
    bot_c <-->|long-polling или webhook| tg_servers
    bot_c --> pg_c
    bot_c --> redis_c
    web_c --> pg_c
```

Один VPS, один `docker-compose.yml`, четыре сервиса. nginx — на хосте или тоже в compose (решается в [07-deployment.md](07-deployment.md), TASK-026).

## Принципы

1. **Единая бизнес-логика.** Бот и админка имеют один источник правды — `src/shared/services/`. Никакой логики «в обход».
2. **Внешние интеграции — через интерфейс.** Реестр пользователей — за абстракцией; в dev — mock, в prod — реальный HTTP-клиент. Это позволяет работать до согласования контракта и тестировать без внешней системы.
3. **Транзакционность.** Любая операция, меняющая несколько таблиц (фиксация итога + отметка прогнозов + аудит), — в одной транзакции.
4. **Архив — мягкий.** Архивируемые события и прогнозы не удаляются; нужен флаг `is_archived` и фильтр в запросах. Это даёт пересмотр истории и статистику.
5. **Нет общего состояния в памяти.** FSM хранится в Redis, не в локальной памяти. Это позволит при необходимости запустить несколько инстансов бота.
6. **Логирование структурное.** Все логи — JSON, с `request_id` / `update_id` / `user_id`. Это упрощает разбор post-mortem.

## Связанные документы

- [02-tech-stack.md](02-tech-stack.md), [03-data-model.md](03-data-model.md), [06-external-api.md](06-external-api.md), [07-deployment.md](07-deployment.md)
- [ADR-0002 monorepo layout](adr/0002-monorepo-layout.md)
