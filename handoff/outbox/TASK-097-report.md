---
task: TASK-097
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/TBD
branch: feature/TASK-097-admin-stats-bot-digest
commits:
  - TBD feat: TASK-097 admin stats via bot (daily digest + event result notifications)
---

# Отчёт по TASK-097: Админ-статистика через бота — дневной дайджест + пост-итоговая сводка события

## Сводка

Реализована развязка админ-уведомлений через БД + scheduler бота (как broadcast'ы). 

- Config: `admin_telegram_chat_ids: list[int]` (CSV via NoDecode + validator, дефолт `[]` = фича off, валидно везде).
- Модель + миграция 0007: `events.result_notified_at` (nullable, без CHECK).
- Repos: `UserRepository.count_new_since`, `PredictionRepository.count_for_event + outcome_distribution_for_event + correct_users_for_event`.
- StatsService: `event_result_summary` → `EventResultSummary` + `CorrectUserRow` (с is_winner по result_outcome_id).
- CSV: `src/bot/_csv.py` (utf-8-sig BOM, заголовки по спеке, None→'', готов BufferedInputFile).
- Jobs: `send_daily_admin_digest` (Cron 16:00 Europe/Moscow), `dispatch_event_result_notifications` (Interval 1min, claim via FOR UPDATE SKIP LOCKED, per-event commit после отправки, ошибки в одном чате не блокируют mark notified).
- Тексты: 5 именованных констант в `texts.py`.
- Unit-тесты: парсер config (пусто/CSV/мусор), генератор CSV (BOM, header, escape, 0 rows→None).
- Регистрация в builder (с timezone= на Cron, coalesce/max=1).

Всё через DI session, идемпотентно, warning на пустом списке получателей (события не трогаем для notifications).

## Изменённые файлы

```
* src/shared/config.py
* src/shared/models/event.py
+ src/migrations/versions/0007_event_result_notified_at.py
* src/shared/repositories/user.py
* src/shared/repositories/prediction.py
* src/shared/services/stats.py
* src/shared/services/__init__.py
+ src/bot/_csv.py
* src/bot/scheduler/jobs.py
* src/bot/scheduler/builder.py
* src/bot/texts.py
* infra/.env.example
* infra/.env.bot.example
* infra/docker-compose.yml
* tests/unit/test_config.py
+ tests/unit/bot/test_csv.py
+ handoff/outbox/TASK-097-report.md
```

## Как воспроизвести / запустить

```bash
# 1. Применить миграцию
uv run alembic upgrade head

# 2. Задать получателей (для теста)
export ADMIN_TELEGRAM_CHAT_IDS=123456789

# 3. Запустить бота (dev)
make up
# или uv run python -m src.bot.main

# 4. Тесты
uv run pytest tests/unit/test_config.py tests/unit/bot/test_csv.py -q
uv run ruff check
uv run mypy src/shared --strict

# Ручной тест дайджеста (в коде): временно поменять триггер на Interval(seconds=30), проверить отправку.
```

## Что не сделано (если применимо)

- Нет интеграционных тестов на jobs (требуют замоканного Bot + session + fixtures событий/пользователей/прогнозов) — за рамками времени; покрыты unit на нижележащие слои + csv/config.
- Нет "is_primary" guard'а на джобах (в отличие от heartbeat в stash 096) — не требовалось в DoD, оба инстанса могут слать (админы получат дубли, но ок для MVP).
- Не обновлял prod compose / .env.prod.example (не в спеке задачи).
- В `correct_users_for_event` repo возвращает list[dict] (тонкий слой), service маппит в dataclass — ок по конвенциям.

## Открытые вопросы для проектировщика

- Нет. Всё по спеке + DoD. При приёмке на проде проверить: 1) доставку в реальные ADMIN_TELEGRAM_CHAT_IDS, 2) CSV в Excel (BOM), 3) поведение при 0 угадавших (без файла), 4) идемпотентность при рестарте scheduler'а посередине отправки.

## Предложение для PROJECT_STATUS.md

2026-06-01 — **TASK-097 ЗАКРЫТ.** Админ-статистика через бота: ежедневный дайджест (cron 16:00 MSK: total/new/preds 24h) + пост-итоговые сводки (Interval 1min, claim SKIP LOCKED, текст+CSV угадавших). `ADMIN_TELEGRAM_CHAT_IDS` (CSV list[int], []=off). Миграция 0007, модель, StatsService.event_result_summary + CorrectUserRow, Prediction/User repo методы, src/bot/_csv (utf-8-sig), 2 джоба + регистрация, тексты, unit-тесты (parser+CSV). PR #TBD. Ревью: чисто, mypy/ruff/pytest unit зелёные.
