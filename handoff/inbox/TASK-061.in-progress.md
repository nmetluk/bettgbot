---
id: TASK-061
created: 2026-05-29
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/03-data-model.md
  - docs/04-bot-flows.md
  - docs/05-admin-spec.md
  - sessions/2026-05-29-01-admin-design/artifacts/admin/page-roadmap.jsx
priority: high
estimate: L
---

# TASK-061: Рассылки и анонсы (broadcast по сегменту)

## Контекст

Следующая пост-MVP фича по убыванию пользы (Высокий/M из roadmap-экрана прототипа — фактически L,
т.к. это вертикальный срез: модель + миграция + сервис + фоновый job в боте + админ-экран).
Roadmap: «Экран составления broadcast-сообщения по сегменту (все / активные / по категории)
с предпросмотром в Telegram и историей отправок. Закрывает "как сообщить о новом событии"».

**Ключевое архитектурное решение — рассылка развязана через БД + scheduler бота, а НЕ отправляется
из web-процесса напрямую.** Причины:
1. Рассылка тысячам пользователей идёт минутами, с пейсингом под Telegram rate-limit (~30 msg/s) и
   ретраями — это **не** место для синхронного HTTP-запроса админки.
2. Бот-процесс уже держит `Bot`-инстанс, `AsyncIOScheduler` и проверенный паттерн идемпотентной
   доставки (`dispatch_reminders` + `ReminderDispatchLog`: `record` ДО `send_message`).
3. (Контекст, не блокер) TASK-050 сегрегировал секреты; недавний `4ec5e9d` вернул токен в web —
   но это тех-долг, на него опираться не надо. Архитектурно правильно: web только **ставит задачу
   в очередь** (пишет строку `Broadcast`), бот её **исполняет**.

Поэтому: админка создаёт `Broadcast` (status `draft`→`queued`), новый job бота
`dispatch_broadcasts` подхватывает `queued`, рассылает с пейсингом и логированием по получателям,
двигает статус `sending`→`done`/`failed` и счётчики.

## Цель

Админ может составить сообщение, выбрать сегмент аудитории, увидеть предпросмотр, поставить рассылку
в очередь; бот доставляет её в фоне; админка показывает историю с прогрессом и итогами.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО написать `handoff/outbox/TASK-061-report.md`.**
> Без отчёта CI handoff-consistency красный, PR не мёрджится.
> 🚨 Задача не закрыта, пока CI зелёный и PR смёрджен (см. `handoff/README.md`).
> 🚨 Move-семантика inbox→archive: перед archive — `ls handoff/inbox/ | grep TASK-061`, `git rm` все копии; archive — **директорией** (`handoff/archive/TASK-061-broadcasts/task.md`).

Задача крупная (L). **Допустимо разбить на 2 PR** в рамках одной задачи/ветки: (A) данные + бот-доставка,
(B) админ-экран. Но закрыть задачу можно только когда зелёный весь срез.

### A. Данные + доставка

- [ ] Модель `Broadcast` (`src/shared/models/`): `id`, `segment` (Enum/`Literal`-mapped: `all`/`active`/`category`),
      `category_id` (nullable FK → Category, обязателен при `segment=category`), `message_text` (Text),
      `status` (`draft`/`queued`/`sending`/`done`/`failed`), `created_by_admin_id` (FK → AdminUser),
      `created_at`, `started_at`/`finished_at` (nullable), счётчики `total_recipients`/`sent_count`/`failed_count`.
      CHECK-инвариант: `segment=category ⇒ category_id IS NOT NULL`. Сверить с инвариантами `docs/03-data-model.md`,
      при необходимости — дописать раздел (это правка `docs/` — **в скоупе именно этой задачи**, отметь в отчёте).
- [ ] (Идемпотентность доставки) Таблица `broadcast_delivery` ИЛИ переиспользование паттерна dispatch-log:
      `(broadcast_id, user_id)` UNIQUE + `record` ДО `send_message` — чтобы рестарт бота в середине
      рассылки не дублировал сообщения. Зеркаль `ReminderDispatchLog`.
- [ ] Миграция `0005_broadcasts` (head сейчас `0004`; цепочка `0001→0002→0003→0003b→0004`).
      Применяется и проверяется integration-тестом `test_migrations` (как для прошлых).
- [ ] `BroadcastRepository`: `create_draft`/`enqueue`, `claim_next_queued` (атомарно взять одну `queued`→`sending`),
      `recipients_for(segment, category_id)` (один SQL: `all` = `is_blocked=False`; `active` = `is_blocked=False AND last_seen_at >= now()-30d`; `category` = distinct user_id с прогнозом в событии данной категории, `is_blocked=False`), `record_delivery`, `mark_done/failed` + инкременты счётчиков, `list_for_admin` (история, новые сверху).
- [ ] `BroadcastService` (бизнес-логика, типизированные dataclass'ы; роут без логики): создание/постановка в очередь
      с валидацией (непустой текст ≤ лимит Telegram 4096; `category` требует существующую активную категорию),
      подсчёт `total_recipients` при enqueue.
- [ ] Job `dispatch_broadcasts(bot, ...)` в `src/bot/scheduler/jobs.py` + регистрация в `builder.py`
      (интервал, напр. каждые 1 мин, `max_instances=1`, `coalesce=True`, разумный `misfire_grace_time`).
      Логика: взять одну `queued`→`sending`; итерировать получателей; на каждого `record_delivery` ДО `send_message`;
      `send_message(parse_mode=None)` — **плоский текст** (без HTML), чтобы исключить инъекцию (rich-форматирование —
      будущая задача); `except TelegramAPIError` → `failed_count++`, лог не откатываем (юзер заблокировал бота — норма);
      **пейсинг** (`asyncio.sleep` ~0.05s/сообщение, ≤ ~20–30 msg/s); по завершении `mark_done` + `finished_at`.
      Гард: пустой сегмент (0 получателей) → сразу `done`.
- [ ] Текст сообщения: даже при `parse_mode=None` экранирования не требуется (плоский текст), но если решишь
      слать с `parse_mode=HTML` — **обязателен** `html.escape`/`aiogram.html.quote` (см. `src/bot/_text_safety.py`,
      TASK-036). Выбор отрази в отчёте.

### B. Админ-экран

- [ ] `GET /broadcasts` (`src/admin/routes/`, регистрация в `app.py`), под `current_admin` — **история** отправок
      (`.pv-table`: дата, автор, сегмент, статус-бейдж, `sent/failed/total`, прогресс). Пустое состояние.
- [ ] `GET /broadcasts/new` — форма составления: textarea сообщения, выбор сегмента (radio/select; при `category` —
      dropdown активных категорий), счётчик символов, **кнопка предпросмотра**.
- [ ] **Предпросмотр в стиле Telegram** (как в roadmap): рендер сообщения в «пузыре» + показ числа получателей
      выбранного сегмента **до** отправки (HTMX-фрагмент: POST/GET считает `recipients_for(...)` и рисует превью).
- [ ] `POST /broadcasts` — CSRF, валидация, создаёт `Broadcast` со `status=queued`, audit-запись (как у прочих
      admin-действий, через `AuditLog`); редирект в историю с flash. **Из web ничего в Telegram не шлётся.**
- [ ] Пункт «Рассылки» в навигации `base.html`, раздел «Управление», иконка из прототипа — `campaign`.
- [ ] CSP: предпросмотр и любые скрипты — **по паттерну TASK-060** (внешний JS с `'self'` + `<script type="application/json">`
      для данных; инлайн-`<script>` запрещён). CSP-заголовок не менять.

### Качество

- [ ] Integration-тесты: `recipients_for` для всех 3 сегментов (фикстуры с blocked/active/inactive юзерами,
      прогнозами в разных категориях); `claim_next_queued` (атомарность/один claimer); идемпотентность доставки
      (повторный `record_delivery` не дублирует); счётчики после `dispatch_broadcasts` (мок `bot.send_message`,
      часть бросает `TelegramAPIError`); миграция применяется. Unit на хэндлеры (история 200, форма 200,
      предпросмотр считает получателей, POST создаёт queued + audit, пустое состояние).
- [ ] `uv run pytest` зелёный полностью; `ruff`/`mypy` чисто (mypy strict для `src/shared/`); PR `TASK-061: ...`;
      CI зелёный; PR смёрджен; локальная `main` синхронизирована.
- [ ] Отчёт + archive директорией. Меняешь текст шаблонов — синхронно правь текстовые ассерты тестов.

## Вне скоупа

- Rich-форматирование/Markdown/вложения/кнопки в рассылке (пока плоский текст).
- Отложенная отправка по расписанию, отмена уже идущей рассылки, повтор только упавшим.
- Сегменты сложнее трёх (например, по точности/активности за произвольный период).
- Рассылка изнутри web-процесса напрямую (архитектурно отвергнуто — см. Контекст).

## Артефакты

- `+ src/shared/models/broadcast.py` (+ delivery-log при отдельной таблице); `* src/shared/models/__init__.py`
- `+ src/migrations/versions/0005_broadcasts.py`
- `+ src/shared/repositories/broadcast.py`; `+ src/shared/services/broadcast.py`
- `* src/bot/scheduler/jobs.py` + `* src/bot/scheduler/builder.py` — job `dispatch_broadcasts`
- `+ src/admin/routes/broadcasts.py`; `* src/admin/app.py` — регистрация
- `+ src/admin/templates/broadcasts/{list,form,_preview}.html`; `* base.html` — навигация
- `+ src/admin/static/js/broadcasts.js` (если нужен JS для предпросмотра — по паттерну TASK-060)
- `* docs/03-data-model.md` — раздел про `Broadcast` (правка docs в скоупе этой задачи)
- `+ tests/...` — integration + unit

## Ссылки

- Паттерн фоновой доставки: `dispatch_reminders` в [`src/bot/scheduler/jobs.py`](../../src/bot/scheduler/jobs.py),
  идемпотентность — `ReminderDispatchLog` (TASK-017), миграция `0002`.
- Регистрация job'ов: [`src/bot/scheduler/builder.py`](../../src/bot/scheduler/builder.py).
- CSP-паттерн для предпросмотра: TASK-060 (`src/admin/static/js/analytics.js` + `<script type="application/json">`).
- HTML-safety: [`src/bot/_text_safety.py`](../../src/bot/_text_safety.py) (TASK-036).
- Сегментация: `User.is_blocked`/`last_seen_at`; «по категории» — distinct user_id через Prediction→Event→Category
  (паттерн JOIN как в `category_accuracy`, TASK-059).
- Audit admin-действий: `AuditLog` + `AuditLogService` (как в категориях/событиях).
- Roadmap-эталон UI: `sessions/2026-05-29-01-admin-design/artifacts/admin/page-roadmap.jsx`.

## Подсказки исполнителю

- `claim_next_queued` делай атомарно (`UPDATE ... WHERE status='queued' ... RETURNING` / `SELECT ... FOR UPDATE SKIP LOCKED`
  + переход в `sending`), чтобы при `max_instances=1` всё равно не было гонок.
- Telegram rate-limit: ~30 msg/s в одного бота суммарно; держи пейсинг с запасом (~20/s). Большие рассылки
  растянутся на несколько тиков job'а — это нормально, благодаря delivery-log идемпотентности.
- Предпросмотр числа получателей — отдельный лёгкий запрос `count` (не материализуй весь список в форме).
- Если что-то требует ослабления CSP или менять контракт внешнего API — **открытый вопрос**,
  оформи `handoff/outbox/TASK-061-question.md`, не решай молча.
- `parse_mode=None` (плоский текст) — самый безопасный дефолт против инъекции; rich-формат вынесен из скоупа сознательно.
