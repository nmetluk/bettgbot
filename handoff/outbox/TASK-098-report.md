---
task: TASK-098
completed: 2026-06-01
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/TBD
branch: feature/TASK-098-admin-stats-enrichment
commits:
  - TBD feat: TASK-098 admin stats enrichment
---

# Отчёт по TASK-098: Обогащение админ-статистики (дайджест + пост-итоговая сводка)

## Сводка

Расширена базовая админ-статистика из TASK-097. Добавлены дельты, DAU, активные события, топ-3, точность закрытых, конверсия в дайджест; majority vs winner и participation % в пост-итоговую сводку.

Вся логика подсчёта вынесена в StatsService (как требовалось), репозитории предоставляют тонкие агрегаты, джобы только форматируют с использованием текстов из texts.py. Форматирование дельт и нулевых случаев покрыто unit-тестами.

## Изменённые файлы

```
* src/shared/repositories/user.py                    # count_active_since (рефакторинг 30d)
* src/shared/repositories/prediction.py              # count_predictions_since, top_events_in_window, prediction_accuracy_for_closed, count_new_and_converted_since
* src/shared/repositories/event.py                   # count_currently_open
* src/shared/services/stats.py                       # DailyAdminDigest dataclass, daily_admin_digest(), обогащение EventResultSummary
* src/shared/services/__init__.py                    # экспорт DailyAdminDigest
* src/bot/scheduler/jobs.py                          # обновлён digest + event notifications на сервис + форматирование
* src/bot/texts.py                                   # новые строки и обновлён ADMIN_DAILY_DIGEST
+ tests/integration/services/test_stats_service.py   # тесты на новые агрегаты + enriched summary
* tests/unit/bot/scheduler/test_admin_digest.py      # обновлены на моки сервиса + покрытие enrichment и форматирования
+ handoff/outbox/TASK-098-report.md
```

## Как воспроизвести / запустить

```bash
uv run alembic upgrade head
uv run pytest tests/integration/services/test_stats_service.py tests/unit/bot/scheduler/test_admin_digest.py -q
uv run ruff check
uv run mypy src/shared --strict
```

## Что не сделано (если применимо)

- Нет обновления docs/04-bot-flows.md (по задаче — делает cowork).
- Форматы текстов сделаны разумными на основе DoD, но точный текст в проде может быть уточнён.

## Открытые вопросы для проектировщика

- Нет.

## Предложение для PROJECT_STATUS.md

2026-06-01 — **TASK-098 ЗАКРЫТ.** Обогащение админ-статистики: дельты к прошлым суткам (new/preds), DAU, активные события, топ-3 по активности, точность закрытых за 24ч, конверсия новых в дайджесте; majority vs winner + % участия в пост-итоговой. Логика в StatsService + новые методы в User/Prediction/Event repos. 2 integration + обновлённые unit тесты. PR #TBD.

## Метрики (опционально)

- Тестов добавлено: 2 новых integration + расширение unit (покрыты все новые агрегаты, дельты, zero cases, форматирование)
- Коммитов: несколько в ветке
