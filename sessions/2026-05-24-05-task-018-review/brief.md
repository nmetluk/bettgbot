# Brief — task-018-review (+ закрытие Этапа 2)

**Дата:** 2026-05-24
**Длительность:** короткая сессия cowork
**Участники:** Николай (owner), cowork-agent

## Запрос владельца

Прочитать отчёт по TASK-018 и подготовить TASK-019 (старт Этапа 3).

## Контекст

**🎉 Этап 2 (Telegram-бот) закрыт.** TASK-018 завершил серию из 18 задач от инициализации репо до полностью функционального бота с фоновыми задачами.

TASK-018 после разблокировки выполнен за **8 коммитов** на единой ветке `feature/TASK-018-scheduler-archive` (squash `b9ac46e`):

- Миграция `0003_relax_event_archive_constraint` — расширение CHECK до 3 валидных комбинаций. Downgrade fail-loud (не auto-fix данных).
- Модель `Event.__table_args__` — синхронизирован новый CheckConstraint.
- `EventRepository.archive_stale(cutoff) -> int` — bulk-UPDATE одним SQL.
- `EventService.archive_stale_events(now=None, threshold_days=7) -> int` — обёртка с commit только при rowcount > 0.
- Job `archive_stale_events_job` в `src/bot/scheduler/jobs.py`.
- Регистрация в `build_scheduler` через `CronTrigger(hour=3, minute=0)`, `misfire_grace_time=300`.
- **8 новых тестов**: 5 integration на сервис (archives old/skips recent/skips resolved/skips already archived/custom threshold) + 2 unit на job + 1 integration на миграцию.
- **Всего: 156 unit + 91 integration = 247 тестов.** Все зелёные.

PR [#52](https://github.com/nmetluk/bettgbot/pull/52) → squash `b9ac46e`. Plus три связанных PR: [#49](https://github.com/nmetluk/bettgbot/pull/49) (pre-task cleanup), [#50](https://github.com/nmetluk/bettgbot/pull/50) (block), [#51](https://github.com/nmetluk/bettgbot/pull/51) (block resolution: Variant A, релакс инварианта). Archive [#53](https://github.com/nmetluk/bettgbot/pull/53).

Полный отчёт — [`handoff/outbox/TASK-018-report.md`](../../handoff/outbox/TASK-018-report.md).

## Решения этой сессии

4 open questions, все на **keep**, плюс 1 пункт в тех-долг BACKLOG:

- **(Q1)** `fresh_db`-фикстура хрупкая: если тест оставит «архивный без result» после миграции 0003 → следующая session не сможет `downgrade base` (старый CHECK ругнётся). Сейчас в одном тесте обход через TRUNCATE; если кто-то напишет похожий с failing assert между insert'ами — данные останутся. **Keep**, но **записать в тех-долг BACKLOG**: «`fresh_db` должна делать `TRUNCATE ... CASCADE` перед `downgrade base`».
- **(Q2)** Migration 0003 downgrade fail-loud — keep. Destructive auto-fix (`DELETE FROM event WHERE is_archived=true AND result_outcome_id IS NULL`) опасен на проде. Оператор сам решит.
- **(Q3)** Стиль `text(sql)` в migrations-тесте vs ORM-фабрики — keep. Прямой SQL явнее для миграционного теста, не нужно тянуть фабрики через сетап БД с partial-схемой.
- **(Q4)** `is_blocked` фильтр пользователя case closed (из TASK-017) — да, подтверждено в DECISIONS.

## Итоги Этапа 2 (TASK-010 — TASK-018)

**9 задач за полтора дня** (TASK-010..018, не считая review-сессий и cleanup-PR'ов):

- **TASK-010** aiogram bootstrap (Dispatcher, middlewares, скелеты роутеров).
- **TASK-011** `/start` + Contact-handler (регистрация).
- **TASK-012** каталог событий (категории → события → карточка).
- **TASK-013** FSM «Сделать прогноз» + декоратор `@require_active_user` + `render_event_card`.
- **TASK-014** «Мои прогнозы» (активные/архив + статистика). **Выполнено на удалённой машине через Drive backup.**
- **TASK-015** «🔔 Напоминания» (toggle + пресеты + FSM свободного ввода).
- **TASK-016** `/help` + рефакторинг `InvalidReminderOffsetsError.reason: Literal`.
- **TASK-017** APScheduler-job рассылки напоминаний (модель `ReminderDispatchLog` + миграция 0002).
- **TASK-018** APScheduler-job автоматической архивации (миграция 0003, разблокировано через Variant A).

**Чему научился проект:**

- **Двухмашинный workflow** через Google Drive coverage — реальный сценарий проверен (TASK-014).
- **Handoff поддерживает блокировку** — TASK-018 заблокирован → cowork разобрал → amendment → доделка.
- **Доменные исключения с `reason: Literal`** — типизированная обработка через `match` (TASK-009, TASK-016).
- **Идемпотентность scheduler-job** через `record` ДО `send_message` (TASK-017).
- **Релакс инвариантов через миграции** — миграция 0003 как образец для будущих data-model изменений (TASK-018).
- **Cowork обязан сверять с инвариантами `docs/03`** до публикации (правило, родившееся из TASK-018 block).

**Итоговая статистика этапа:**

- 247 тестов (156 unit + 91 integration), CI 4 зелёных job'а.
- 3 миграции (0001 init + 0002 reminder_dispatch_log + 0003 relax archive).
- 7 пользовательских handler'ов + 2 фоновых job'а.
- Двухмашинный workflow проверен в продакшне.
- 18 закрытых задач, 4 review-сессии (`12-..13-..14-..15-..`) на стыке этапов, 1 блок-разрешение.

## Что дальше — старт Этапа 3

**Этап 3 — веб-админка** (TASK-019..026 по BACKLOG):

- **TASK-019** — FastAPI скелет + Jinja2 + Bootstrap 5 шаблон. Базовая структура `src/admin/{app,routes,templates,static}`. Заглушки routes без бизнес-логики. `scripts/create_admin.py` для создания первого админа. **Шаблон выбран — Volt Free** (Themesberg, Bootstrap 5, MIT, чистый). Альтернативы AdminLTE 4 (ещё beta) / SB Admin 2 (Bootstrap 4) отвергнуты. Размер M.
- **TASK-020** — аутентификация админа (логин/пароль, bcrypt через `passlib`, signed cookie через `itsdangerous`, fastapi-limiter поверх Redis для rate-limit, `/login` POST + `/logout`).
- **TASK-021** — CRUD категорий.
- **TASK-022** — CRUD событий (drafts + publish) с фильтрами (категория, статус, период).
- **TASK-023** — CRUD исходов через HTMX inline-редактирование.
- **TASK-024** — фиксация итога + автоматическая отметка прогнозов (использует готовый `EventService.set_result` + `PredictionRepository.mark_correctness`).
- **TASK-025** — список пользователей с поиском по телефону/username, блокировка/разблокировка.
- **TASK-026** — UI аудит-лога с фильтрами по admin/action/датам.

Этап 3 ожидаемо самый длинный (8 задач). После — Этап 4 production (TASK-027..031).

## Следующий шаг

Локальный CC берёт **TASK-019**: FastAPI скелет + Volt Free шаблон + базовая инфра.
