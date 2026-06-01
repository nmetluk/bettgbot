# 05 — Спецификация веб-админки

Минимальная веб-админка для управления категориями, событиями, исходами, фиксации результата и просмотра пользователей. Стек — FastAPI + Jinja2 + HTMX + Bootstrap 5 (см. [02-tech-stack.md](02-tech-stack.md)).

## Принципы

- **Server-side rendering.** HTML отдаётся сервером, точечные обновления — через HTMX. Никакого SPA. Клиентские состояния (тема, плотность таблиц, мелкие тогглы) — на Alpine.js, без выхода на SPA.
- **Дизайн-система v2.** MVP стартовал на готовом Bootstrap 5-шаблоне (TASK-018). Начиная с v2 принят собственный визуальный язык из прототипа дизайнеров: дизайн-токены `--pv-*`, светлая/тёмная тема, плотность таблиц, настраиваемый акцент (см. [ADR 0005](adr/0005-admin-v2-stack.md)). Токены портируются в собственный CSS поверх Bootstrap; React-прототип в `sessions/2026-05-29-01-admin-design/` — визуальный эталон.
- **Никакой бизнес-логики в роутах.** Роут парсит форму, вызывает сервис из `src/shared/services/`, рендерит шаблон. Транзакции — внутри сервиса.
- **Аудит обязателен** для всех write-операций. Запись в `audit_log` — в той же транзакции, что и сама операция.

## Аутентификация

- Логин/пароль. Пароль — bcrypt (`passlib`). Подбор пароля защищён rate-limit-middleware (например, fastapi-limiter поверх Redis).
- Сессия — signed cookie (`itsdangerous`). Срок жизни — 8 часов, продление при активности.
- Регистрация админов через UI **отсутствует**. Первый админ заводится скриптом `scripts/create_admin.py` (создаётся в TASK-019). Дальнейших админов добавляет существующий админ из UI («Администраторы» → «Добавить»; на MVP — опционально, см. backlog).
- Выход — `/logout`, очищает cookie.

## Структура страниц

```
GET  /login                 — форма входа
POST /login                 — обработка
POST /logout

GET  /                      — дашборд (минимум: счётчики)

GET  /categories            — список
GET  /categories/new        — форма создания
POST /categories            — создание
GET  /categories/{id}       — карточка/редактирование
POST /categories/{id}       — обновление
POST /categories/{id}/delete

GET  /events                — список с фильтрами (категория, статус)
GET  /events/new            — форма создания
POST /events                — создание
GET  /events/{id}           — карточка: данные + список исходов + блок результата
POST /events/{id}           — обновление данных
POST /events/{id}/publish   — публикация (черновик → опубликовано)
POST /events/{id}/unpublish
POST /events/{id}/result    — фиксация итога (radio: один из Outcome)

POST /events/{id}/outcomes              — добавить исход (HTMX-fragment)
POST /events/{id}/outcomes/{oid}        — обновить
POST /events/{id}/outcomes/{oid}/delete — удалить (если нет прогнозов)

GET  /users                 — список пользователей с поиском по телефону/username
GET  /users/{id}            — карточка пользователя + список его прогнозов
POST /users/{id}/block
POST /users/{id}/unblock

GET  /audit                 — журнал аудита, фильтры по admin/action/датам
```

## Дашборд (главная)

Минимальный набор счётчиков:

- Пользователей всего / активных (за 30 дней)
- Категорий
- Событий: всего / опубликованных / архивных
- Прогнозов всего / за сутки
- Последние 10 записей аудит-лога

Один SQL-запрос на счётчик, всё в одном шаблоне `templates/dashboard.html`.

## Категории

- Таблица: `id | name | slug | active | sort | events_count | actions`.
- Сортировка по `sort_order`, ручное перетаскивание — не на MVP, только числовое поле.
- Удалить можно только пустую категорию (без событий) — иначе кнопка `Delete` отдаёт 409.

## События

### Список

Таблица с фильтрами в шапке:

| Фильтр | Значения |
|---|---|
| Категория | dropdown |
| Статус | `все / черновики / опубликованные / архивные` |
| Период | `все / ближайшие 7 дней / прошедшие` |

Колонки: `id | title | category | starts_at | predictions_close_at | status | predictions_count | actions`.

Статус — bage:

- `черновик` — серая
- `опубликовано, открыт приём` — зелёная
- `опубликовано, приём закрыт` — жёлтая
- `архив` — синяя

### Карточка события

Три блока, каждый на своей вкладке (Bootstrap nav-tabs):

#### Вкладка «Данные»

Форма: `title`, `description`, `category`, `starts_at`, `predictions_close_at`, `metadata` (JSON-текстарея — pretty-print). Кнопки: `Сохранить`, `Опубликовать` / `Снять с публикации`.

#### Вкладка «Исходы»

Список исходов с inline-редактированием (HTMX): `label`, `sort_order`. Кнопка «Добавить». Удаление — если на исход **нет** прогнозов.

Кнопки `Опубликовать` неактивна, пока исходов меньше двух.

#### Вкладка «Результат»

Видна только когда событие опубликовано и приём прогнозов закрыт (либо `predictions_close_at` прошёл, либо `starts_at` прошёл — на выбор админа).

Форма: радио-кнопки со списком `Outcome`, кнопка «Зафиксировать».

При подтверждении (`POST /events/{id}/result`):

1. `EventService.set_result(event_id, outcome_id, admin_id)`:
   - В транзакции: `event.result_outcome_id`, `event.is_archived = true`, `event.archived_at = now()`.
   - `PredictionService.mark_predictions(event_id, outcome_id)` — обновляет `is_correct` для всех прогнозов.
   - `AuditLog.add(action=event.set_result, payload={event_id, outcome_id, marked=N})`.
2. Редирект на карточку события с зелёным баннером «Итог зафиксирован, N прогнозов проверено».

После фиксации поле результата становится read-only. **Переопределение итога не предусмотрено в MVP** (если потребуется — отдельная задача с явным «откатом» и аудитом).

**Уведомление админов (TASK-097).** Веб-админка **не шлёт** Telegram-сообщения напрямую (у неё нет `Bot`). Фиксация итога лишь проставляет `result_outcome_id`; пост-итоговую статистику и CSV угадавших рассылает бот отдельным джобом, обнаруживая события с `result_outcome_id IS NOT NULL AND result_notified_at IS NULL`. Деталь флоу и формат — [04-bot-flows.md](04-bot-flows.md), раздел «Админская статистика». Это сохраняет границу процессов (web ↔ bot) и делает админский POST быстрым и устойчивым к падению Telegram.

## Пользователи

### Список

Поиск по: телефону (E.164 substring), Telegram username, имени.

Колонки: `id | tg_user_id | phone | first_name last_name | username | predictions | created_at | blocked`.

### Карточка пользователя

Профиль + таблица его прогнозов: `event | category | outcome | event status | is_correct`.

Кнопки `Заблокировать` / `Разблокировать`. Заблокированный пользователь не может делать новые прогнозы и не получает напоминаний; в боте при попытке действия — «Ваш доступ ограничен».

## Аудит

Таблица: `created_at | admin | action | payload (preview)`. Фильтры: admin, action, диапазон дат. Полный `payload` — раскрытие строки HTMX-фрагментом.

## Локализация

UI админки — только русский на MVP. Тексты — в Jinja-шаблонах напрямую (вынесение в отдельный словарь — отложено в backlog).

## Безопасность

- HTTPS — обязателен (терминируется nginx-ом на VPS, см. [07-deployment.md](07-deployment.md)).
- CSRF — `fastapi-csrf-protect` или собственный middleware на signed token в форме (TASK-019).
- Cookie-настройки: `Secure`, `HttpOnly`, `SameSite=Lax`.
- Все формы — `POST`, никаких `GET` для изменений.
- Пароль хешируется bcrypt с cost ≥ 12.
- При неуспешной попытке входа — generic-сообщение «неверный логин или пароль» (не раскрывать, что именно).
- Rate-limit на `/login` (например, 5 попыток в минуту с IP).

## Шаблон проекта (черновик файлов)

```
src/admin/
├── app.py                      # FastAPI()
├── deps.py                     # DI: current_admin, db_session
├── auth/
│   ├── routes.py
│   ├── security.py
│   └── middleware.py
├── routes/
│   ├── dashboard.py
│   ├── categories.py
│   ├── events.py
│   ├── outcomes.py
│   ├── users.py
│   └── audit.py
├── templates/
│   ├── base.html
│   ├── _macros.html
│   ├── login.html
│   ├── dashboard.html
│   ├── categories/...
│   ├── events/...
│   ├── users/...
│   └── audit/...
└── static/
    └── (статика темы + минимальный custom.css)
```

## Дизайн следующей версии (v2)

> ✅ **Статус — принят вариант C** ([ADR 0005](adr/0005-admin-v2-stack.md)): SSR-архитектура
> сохраняется, визуальный язык прототипа принят как дизайн-спека. Реализация — задачами
> TASK-053…TASK-056 в `handoff/inbox/`.

Дизайнеры передали интерактивный прототип админки для следующей версии. Он лежит в
[`sessions/2026-05-29-01-admin-design/artifacts/admin/`](../sessions/2026-05-29-01-admin-design/artifacts/admin/):

- `index.html` — многофайловая версия прототипа (React + Babel standalone, без сборки);
- `bettgbot-admin-standalone.html` — та же админка одним файлом;
- `screens/` — скриншоты ключевых экранов.

Контекст и сопроводительные заметки — в сессии
[`sessions/2026-05-29-01-admin-design/`](../sessions/2026-05-29-01-admin-design/)
(`brief.md`, `decisions.md`).

**Решение по стеку:** прототип отрисован на React/SPA, но в продакшен он **не** переносится как
SPA. Принят вариант C ([ADR 0005](adr/0005-admin-v2-stack.md)): продакшен остаётся на SSR
(FastAPI + Jinja2 + HTMX + Alpine.js), из прототипа берётся визуальный язык — токены, тёмная тема,
плотность, сетка, экраны. Прототип служит замороженным визуальным эталоном.

## Связанное

- [01-architecture.md](01-architecture.md), [03-data-model.md](03-data-model.md), [07-deployment.md](07-deployment.md)
- Дизайн v2: [sessions/2026-05-29-01-admin-design/](../sessions/2026-05-29-01-admin-design/)
- [ADR 0005 — Стек веб-админки v2](adr/0005-admin-v2-stack.md)
