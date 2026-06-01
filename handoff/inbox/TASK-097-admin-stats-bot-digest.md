---
id: TASK-097
created: 2026-06-01
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/04-bot-flows.md
  - docs/05-admin-spec.md
  - docs/03-data-model.md
  - state/DECISIONS.md
priority: normal
estimate: L
---

# TASK-097: Админ-статистика через бота — дневной дайджест + пост-итоговая сводка события

## Контекст

Владелец хочет, чтобы бот сам присылал админам статистику. Решение и развязка зафиксированы в [`state/DECISIONS.md`](../../state/DECISIONS.md) (строка 2026-06-01, «Админ-статистика через бота») и спеках: [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) раздел «Админская статистика», [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) (фиксация итога), [`docs/03-data-model.md`](../../docs/03-data-model.md) (колонка `events.result_notified_at`).

**Ключевой принцип — развязка процессов.** Бот и веб-админка — **разные сервисы/процессы**; `Bot` есть только у бота. Поэтому веб-админка Telegram-сообщения **не шлёт**. Используем тот же паттерн, что у рассылок (`dispatch_broadcasts`): источник истины — БД, доставку делает scheduler-джоб бота.

Получатели всех админ-сообщений — env `ADMIN_TELEGRAM_CHAT_IDS` (список `chat_id` через запятую). Пусто → фича выключена, в лог `warning`, БД не трогаем.

## Цель

1. Ежедневный дайджест в 16:00 `Europe/Moscow`: всего пользователей, новых за 24ч, прогнозов за 24ч.
2. После фиксации итога события бот рассылает админам сводку (всего прогнозов / угадали / распределение по исходам) + CSV угадавших.

Обе доставки — джобами бота, идемпотентно, во все `ADMIN_TELEGRAM_CHAT_IDS`.

## Definition of Done

> 🚨 **Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-097-report.md`.** Без отчёта CI handoff-consistency красный. Шаблон — `handoff/templates/report.md`.

### Конфиг
- [ ] `Settings`: `admin_telegram_chat_ids: list[int]` из env `ADMIN_TELEGRAM_CHAT_IDS` (CSV-парсинг, как `MOCK_REGISTRY_ALLOWED` раньше — `NoDecode` + `field_validator`). Пустой/неустановленный → `[]`. Значение `[]` валидно во всех окружениях (фича просто off).
- [ ] env-примеры (`infra/.env.example`, `.env.bot.example`, `infra/docker-compose.yml` для сервиса `bot`): добавить `ADMIN_TELEGRAM_CHAT_IDS=` с комментарием. **Только сервис `bot`** — у `web` он не нужен.

### Миграция и модель
- [ ] Миграция **0007** (следующий свободный номер; revision id ≤ 32 символов — см. DECISIONS): `events.result_notified_at TIMESTAMP WITH TIME ZONE NULL`. Apply+rollback без ошибок.
- [ ] Модель `Event`: поле `result_notified_at: Mapped[datetime | None]`. В CHECK-инвариант **не** включать.

### Данные / StatsService
- [ ] Дайджест-агрегаты:
  - всего пользователей — переиспользовать `UserRepository.count_for_admin(query=None)` (или явный `count_all`).
  - новых за 24ч — новый `UserRepository.count_new_since(since)` (или `count_24h`).
  - прогнозов за 24ч — **уже есть** `PredictionRepository.count_24h()`.
- [ ] Пост-итоговая сводка события — `StatsService.event_result_summary(event_id)` → типизированный dataclass: `total_predictions`, `correct_count`, `outcome_distribution: list[(outcome_id, label, count, is_winner)]`, `correct_users: list[CorrectUserRow]`.
  - `CorrectUserRow`: `tg_user_id, first_name, last_name, tg_username, phone, outcome_label, predicted_at` (для CSV; здесь по событию верный исход один, но колонку `outcome` оставляем — пригодится при будущем расширении).
  - Запросы в `PredictionRepository`: распределение по исходам (`group by outcome_id`), список угадавших с JOIN на `User`.
- [ ] Источник «текущего момента» — `utcnow()` из `src/shared/`, окно = `now() - timedelta(hours=24)`.

### Бот-джобы (`src/bot/scheduler/`)
- [ ] `send_daily_admin_digest(*, bot, session_maker)` в `jobs.py`; регистрация в `builder.py`: `CronTrigger(hour=16, minute=0, timezone="Europe/Moscow")`, `id="send_daily_admin_digest"`, `coalesce=True`, `misfire_grace_time=3600`, `max_instances=1`. Считает агрегаты, форматирует текст (из `texts.py`), шлёт во все чаты. Пустой список чатов → `warning`, return.
- [ ] `dispatch_event_result_notifications(*, bot, session_maker)` в `jobs.py`; регистрация: `IntervalTrigger(minutes=1)`, `misfire_grace_time=300`, `coalesce=True`, `max_instances=1`. Алгоритм:
  1. Если `admin_telegram_chat_ids` пуст → `warning`, return (события **не** трогаем).
  2. Выбрать события `result_outcome_id IS NOT NULL AND result_notified_at IS NULL` с `FOR UPDATE SKIP LOCKED` (как `claim_next_queued` у broadcasts), небольшим батчем.
  3. Для каждого: посчитать `event_result_summary`, собрать текст + CSV, отправить во все чаты, затем `result_notified_at = now()` и commit (по событию, не пачкой — чтобы крэш не терял прогресс).
  4. Ошибка отправки в один чат → лог `warning`, продолжаем по остальным; событие всё равно помечаем notified (повторная массовая рассылка хуже пропуска одного чата — но это зафиксируй в отчёте, если решишь иначе).

### CSV
- [ ] Хелпер генерации CSV в памяти (`io.StringIO`/`csv.writer`), UTF-8 **с BOM** (`utf-8-sig`) для Excel. Колонки: `tg_user_id, first_name, last_name, tg_username, phone, outcome, predicted_at` (ISO-8601, UTC). Имя файла `correct_users_event_{id}.csv`. Отправка через `aiogram` `BufferedInputFile` + `bot.send_document`.
- [ ] 0 угадавших → CSV **не** прикладывать, в тексте «✅ Угадали: 0».

### Тексты
- [ ] Все строки в `src/bot/texts.py` (форматы дайджеста и сводки события) как именованные константы — не хардкодить в джобах.

### Тесты / качество
- [ ] integration: миграция 0007 up/down; `event_result_summary` на фикстуре (несколько пользователей, разные исходы, проверка correct/total/распределения/списка угадавших); дайджест-агрегаты (новые за 24ч vs старые).
- [ ] unit: CSV-хелпер (заголовок, BOM, экранирование, порядок колонок); парсинг `ADMIN_TELEGRAM_CHAT_IDS` (пусто/один/несколько/мусор); форматирование текстов.
- [ ] Джобы покрыть с замоканным `Bot` (проверить: пустой список → не шлёт и не трогает БД; notified-флаг ставится; повторный тик не шлёт второй раз).
- [ ] `ruff check` чисто, `mypy src/shared` чисто, `pytest` зелёный.
- [ ] PR `TASK-097: админ-статистика через бота`; отчёт в outbox; move-семантика inbox→archive.

## Артефакты

```
* src/shared/config.py                         # admin_telegram_chat_ids
+ src/migrations/versions/0007_event_result_notified_at.py
* src/shared/models/event.py                   # result_notified_at
* src/shared/repositories/user.py              # count_new_since/count_24h
* src/shared/repositories/prediction.py        # распределение по исходам + список угадавших
* src/shared/services/stats.py                 # event_result_summary + dataclass'ы
+ src/bot/_csv.py (или аналог)                 # генерация CSV
* src/bot/scheduler/jobs.py                    # 2 новых джоба
* src/bot/scheduler/builder.py                 # регистрация джобов
* src/bot/texts.py                             # тексты дайджеста и сводки
* infra/.env.example, .env.bot.example, docker-compose.yml
+ tests/...                                     # integration + unit
```

## Ссылки

- Флоу/формат: [`docs/04-bot-flows.md`](../../docs/04-bot-flows.md) → «Админская статистика»
- Фиксация итога: [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md), `EventService.set_result`
- Модель: [`docs/03-data-model.md`](../../docs/03-data-model.md) → `Event.result_notified_at`
- Решение: [`state/DECISIONS.md`](../../state/DECISIONS.md) (2026-06-01)

## Подсказки исполнителю

- **Паттерн для копирования** — `dispatch_broadcasts` (`jobs.py`) + `BroadcastRepository.claim_next_queued` (`FOR UPDATE SKIP LOCKED`, commit ДО внешнего эффекта). Здесь «очередь» — это сами события с `result_notified_at IS NULL`.
- APScheduler `CronTrigger` принимает `timezone="Europe/Moscow"` per-trigger — не меняй глобальный `AsyncIOScheduler(timezone="UTC")`.
- `PredictionRepository.count_24h()` уже существует — не дублируй.
- Телефон в CSV — это PII. Файл уходит только в `ADMIN_TELEGRAM_CHAT_IDS`. Не логируй содержимое CSV и сам телефон (используй существующий паттерн `phone_hash` если нужно что-то логировать).
- Не трогай `docs/`/`state/`/`README.md` — обновлены проектировщиком.

## Заметка по будущим расширениям (НЕ делать в этой задаче)

Владелец просил «советы по статистике». В дайджест позже можно добавить: дельту к прошлым суткам (▲/▼), активные события и топ по активности, точность закрытых за сутки событий, конверсию «новый → первый прогноз», DAU. В пост-итоговую сводку — самый популярный исход vs верный, % участия (прогнозы/всего юзеров). Это отдельной задачей после обкатки базовой версии — здесь реализуем только запрошенный минимум.
