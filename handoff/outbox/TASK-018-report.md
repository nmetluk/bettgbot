---
task: TASK-018
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/52
branch: feature/TASK-018-scheduler-archive
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/49 (pre-task cleanup для исходной TASK-018)
  - https://github.com/nmetluk/bettgbot/pull/50 (блок TASK-018, поднят вопрос)
  - https://github.com/nmetluk/bettgbot/pull/51 (block resolution: Variant A, релакс инварианта)
commits:
  - 7ab1265 chore(handoff): resume TASK-018 (blocked → in-progress) after block resolution
  - e4e6842 feat(repositories): EventRepository.archive_stale
  - 293765b feat(services): EventService.archive_stale_events
  - 37cac78 feat(scheduler): archive_stale_events job (daily 03:00 UTC)
  - 897209a feat(migrations): 0003_relax_event_archive_constraint
  - d291c54 feat(models): обновить CheckConstraint Event под новый инвариант
  - 0cab368 test(integration): 0003 relax event archive check
  - 89f7585 test: archive_stale_events — 5 integration + 2 unit + builder регистрация
---

# Отчёт по TASK-018: APScheduler-job автоматической архивации стейлевых событий

## Сводка

Закрывает Этап 2 проекта. Добавлен второй (и последний) фоновый job — `archive_stale_events` запускается через `CronTrigger(hour=3, minute=0)` UTC, `misfire_grace_time=300`. Job находит события, которые «забыли» зафиксировать админом: `starts_at < now() - 7 дней`, `result_outcome_id IS NULL`, `is_archived = false`. Помечает их `is_archived=true, archived_at=func.now()` одним bulk-`UPDATE`. Прогнозы по таким событиям остаются с `is_correct = NULL`.

**Блокер и его разрешение.** При первой попытке реализации (см. PR [#50](https://github.com/nmetluk/bettgbot/pull/50)) integration-тесты падали с `CheckViolationError` — существующий `ck_event_result_archive_consistency` запрещал комбинацию `is_archived=true AND result_outcome_id IS NULL`, но спека TASK-018 требовала именно её. Я поднял вопрос (`handoff/archive/TASK-018-scheduler-archive/question.md`), cowork выбрал Variant A (релакс инварианта через миграцию `0003`), обновил `docs/03-data-model.md` (PR [#51](https://github.com/nmetluk/bettgbot/pull/51)). В этом PR — собственно реализация: миграция, обновлённая модель, сервис/репо/scheduler + тесты.

`EventService.archive_stale_events(now=None, threshold_days=7)` принимает `now` параметром (для детерминированных тестов) с дефолтом `datetime.now(tz=UTC)`. Commit делается только если rowcount > 0 (избегаем пустых commit'ов в no-op-тиках). Audit-лог НЕ пишется — автоматическое действие без `admin_id` (если когда-то понадобится — потребует расширения модели `AuditLog`).

## Изменённые файлы

```
* src/shared/models/event.py                                    # CheckConstraint расширен
* src/shared/repositories/event.py                              # +archive_stale
* src/shared/services/event.py                                  # +archive_stale_events
+ src/migrations/versions/0003_relax_event_archive_constraint.py
* src/bot/scheduler/jobs.py                                     # +archive_stale_events
* src/bot/scheduler/builder.py                                  # +CronTrigger регистрация
* src/bot/scheduler/__init__.py                                 # +archive_stale_events в __all__
+ tests/integration/services/test_event_service_archive_stale.py   # 5 тестов
+ tests/unit/bot/scheduler/test_archive_stale_events.py            # 2 теста
* tests/unit/bot/scheduler/test_builder.py                      # +регистрация archive
* tests/integration/test_migrations.py                          # +test_0003_relax_event_archive_check
* handoff/inbox/TASK-018-...md → archive/TASK-018-scheduler-archive/task.md
* handoff/inbox/TASK-018-amendment.md → archive/TASK-018-scheduler-archive/amendment.md
* handoff/outbox/TASK-018-question.md → archive/TASK-018-scheduler-archive/question.md
+ handoff/outbox/TASK-018-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    120 files already formatted
mypy src/shared src/bot          Success: no issues found in 60 source files
pytest -m "not integration"      156 passed in 1.70s
pytest tests/integration         91 passed in 12.83s

CI PR #52 — все четыре job'а зелёные:
  Lint (ruff)                              9s
  Typecheck (mypy)                         16s
  Tests (pytest, unit)                     21s
  Integration (alembic on real postgres)   45s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
cp infra/.env.example .env
make up && make migrate              # применит до 0003 включительно

uv run pytest -m "not integration" -v
uv run pytest tests/integration -m integration -v

# Ручной dry-run (опц.):
# 1) В psql:
#    INSERT INTO admin_user (login, password_hash) VALUES ('t', 'h') RETURNING id;
#    INSERT INTO category (name, slug, sort_order, is_active) VALUES ('Test', 'test', 0, true) RETURNING id;
#    INSERT INTO event (category_id, title, metadata, starts_at, predictions_close_at, is_published, created_by_admin_id)
#      VALUES (<cat>, 'Old', '{}'::jsonb, now() - interval '8 days', now() - interval '8 days', true, <adm>);
# 2) python -c "
#    import asyncio
#    from src.shared.db import SessionLocal
#    from src.shared.services import EventService
#    async def m():
#      async with SessionLocal() as s:
#        print(await EventService(s).archive_stale_events())
#    asyncio.run(m())
#    "
#    → 1
# 3) Проверить: SELECT is_archived, archived_at, result_outcome_id FROM event WHERE title = 'Old';
```

## Что не сделано / вынесено

1. **Audit-лог для автоархивации** — не добавлен. Потребует расширения модели `AuditLog` (nullable `admin_id` или поле `actor` ENUM). Решение оставлено на будущее (нет явного запроса).
2. **Конфигурируемый `threshold_days` через `Settings`** — не сделал, дефолт 7 захардкоден. Преждевременно.
3. **Конфигурируемое время `03:00 UTC`** — тоже захардкожено. Если понадобится — отдельная задача.
4. **Cleanup старых стейл-архивных событий** — не предусмотрено, они остаются в архиве пользователя.
5. **Локально пришлось дважды вручную truncate'ить event/category/admin_user** — мой тест `test_0003_relax_event_archive_check` инсертил данные в реальный Postgres-сетап (вне `nested_session`). При фейле теста (или при первом запуске на «грязной» БД) `fresh_db.downgrade base` падает на 0003→0002, потому что строка «архивный без result» нарушает старый CHECK. В CI не воспроизводится — там postgres каждый раз с нуля. Возможный фикс — обернуть тест в собственный try/finally truncate (сейчас уже есть, но fail-mid-test всё равно оставляет данные).

## Открытые вопросы для проектировщика

1. **`fresh_db`-фикстура хрупкая** — если хоть один тест оставит «архивный без result» после миграции 0003, следующий test session не сможет `downgrade base`. Сейчас обхожу через TRUNCATE в конце моего теста; но если кто-то напишет похожий с failing assert между inserts — данные останутся. Если хотим жёсткой изоляции — `fresh_db` мог бы делать `TRUNCATE … CASCADE` перед `downgrade base`. Согласовать как convention.
2. **Migration 0003 downgrade** упадёт на проде, если автоархивация уже сработала. Принято. Если хотим явный safe-downgrade — добавить SQL вида `DELETE FROM event WHERE is_archived=true AND result_outcome_id IS NULL` в downgrade с комментарием «destructive — only if you accept losing safety-net rows». Не делал — destructive auto-fix не похож на «оператор знает что делает».
3. **`tests/integration/test_migrations.py` сейчас использует `text(sql)` для INSERT** в новом тесте — стиль отличается от других тестов (там через `_alembic` subprocess и через scalar select для проверки). Если хочется унифицировать — переписать через ORM-фабрики. Сейчас прямой SQL более явный.
4. **`is_blocked` фильтр пользователя в TASK-017 теперь "case closed"** через подтверждение в `state/DECISIONS.md`. Спасибо.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-018: завершает Этап 2 (Telegram-бот). Второй фоновый job `archive_stale_events` (CronTrigger 03:00 UTC, misfire 300s) — bulk-UPDATE стейлевых событий без итога. Миграция `0003_relax_event_archive_constraint` (Variant A на блокер): CHECK `ck_event_result_archive_consistency` расширен до трёх валидных комбинаций («архивный без result_outcome_id»). Модель синхронизирована. 8 новых тестов (5 integration archive_stale + 2 unit job + 1 integration migration). PR [#52](https://github.com/nmetluk/bettgbot/pull/52) → squash `b9ac46e`. Pre-task cleanup [#49](https://github.com/nmetluk/bettgbot/pull/49), block [#50](https://github.com/nmetluk/bettgbot/pull/50), block-resolution [#51](https://github.com/nmetluk/bettgbot/pull/51).
```

## Метрики

- Файлов добавлено: 4 (migration + 2 теста + report)
- Файлов изменено: 8 (модель, репо, сервис, jobs, builder, scheduler/init, test_builder, test_migrations)
- Тестов добавлено: 8 unit/integration (всего 156 unit + 91 integration; было 153 + 85)
- Время на выполнение: ~75 мин (включая cleanup PRs, блок + ответ cowork-агента, миграцию, борьбу с fresh_db-фикстурой)
