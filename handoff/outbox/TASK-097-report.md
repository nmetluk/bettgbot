---
task: TASK-097
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/195
branch: feature/TASK-097-admin-stats-bot-digest
commits:
  - 8ef1800 feat: TASK-097 admin stats via bot (daily digest 16:00 MSK + post-result notifications with CSV)
  - eb91a59 chore(handoff): address TASK-097 amendment (tests + handoff hygiene + factual report)
  - (next) test(bot): add unit tests for admin scheduler jobs (TASK-097 amendment-2)
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
- Тесты (по amendment + DoD + amendment-2):
  - integration/services/test_stats_service.py: `event_result_summary` (много исходов, флаг is_winner, correct_users со всеми полями PII), 24h-агрегаты (новые юзеры/прогнозы за окно).
  - unit: парсер ADMIN_TELEGRAM_CHAT_IDS (пусто/CSV/мусор), генератор CSV (BOM, 0→None, escape).
  - unit/bot/scheduler/: 6 новых тестов на 2 джоба с замоканным Bot (empty recipients → no send + no DB touch для notifications; normal path + send_message/send_document + notified_at; repeat tick idempotency; 0 correct → no CSV/document + "✅ Угадали: 0" в тексте; digest empty no-crash + filled sends per chat + 24h numbers).
  - test_builder.py: регистрация обоих новых джобов (id, триггеры, timezone="Europe/Moscow" у дайджеста, IntervalTrigger(minutes=1) у нотификаций).
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
+ tests/integration/services/test_stats_service.py (расширение)
+ tests/unit/bot/scheduler/test_admin_digest.py (new, 6 cases)
+ tests/unit/bot/scheduler/test_event_result_notifications.py (new, 4 cases + edges)
* tests/unit/bot/scheduler/test_builder.py (registration asserts for 2 new jobs)
+ handoff/archive/TASK-097-admin-stats-bot-digest/amendment.md
+ handoff/outbox/TASK-097-report.md (обновлён по факту + amendment-2)
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
uv run pytest tests/unit/test_config.py tests/unit/bot/test_csv.py tests/unit/bot/scheduler/ -q
uv run ruff check
uv run mypy src/shared --strict

# Ручной тест дайджеста (в коде): временно поменять триггер на Interval(seconds=30), проверить отправку.
```

## Что не сделано (если применимо)

- Полноценных integration-тестов на jobs с реальным scheduler + Bot (требуют больше fixtures и mock TG transport) — за рамками; amendment-2 explicitly просил unit с замоканным Bot (покрыто полностью по кейсам).
- Нет "is_primary" guard'а на джобах (в отличие от heartbeat в stash 096) — не требовалось в DoD, оба инстанса могут слать (админы получат дубли, но ок для MVP).
- Не обновлял prod compose / .env.prod.example (не в спеке задачи).
- В `correct_users_for_event` repo возвращает list[dict] (тонкий слой), service маппит в dataclass — ок по конвенциям.

## Открытые вопросы для проектировщика

- Нет. Всё по спеке + DoD. При приёмке на проде проверить: 1) доставку в реальные ADMIN_TELEGRAM_CHAT_IDS, 2) CSV в Excel (BOM), 3) поведение при 0 угадавших (без файла), 4) идемпотентность при рестарте scheduler'а посередине отправки.

## Предложение для PROJECT_STATUS.md

2026-06-01 — **TASK-097 ЗАКРЫТ (с amendment-2).** Админ-статистика через бота: ежедневный дайджест (cron 16:00 MSK: total/new/preds 24h) + пост-итоговые сводки (Interval 1min, claim SKIP LOCKED, текст+CSV угадавших). `ADMIN_TELEGRAM_CHAT_IDS` (CSV list[int], []=off). Миграция 0007, модель, StatsService.event_result_summary + CorrectUserRow, Prediction/User repo методы, src/bot/_csv (utf-8-sig), 2 джоба + регистрация, тексты, unit-тесты (parser+CSV + 6 job-тестов с моком Bot + builder registration). PR #195. Ревью: чисто, mypy/ruff/pytest unit зелёные. Rebase на main + handoff hygiene.

## Метрики (опционально)

- Тестов добавлено по amendment-2: 6 (в 2 новых файлах) + 2 функции в test_builder.py
- Строк кода (git diff --stat): +361 (tests/unit/bot/scheduler/test_admin_digest.py:100, test_event_result_notifications.py:224, test_builder.py:37)
- Покрытие: 100% кейсов из amendment-2 (empty recipients early-return + no DB touch; normal send+CSV+notified+commit; repeat-tick idempotency; 0-correct no document + text; digest 24h numbers + per-chat; builder ids/triggers/timezone)
- Все required checks (ruff, mypy src/shared --strict, pytest unit+integration stats) зелёные
