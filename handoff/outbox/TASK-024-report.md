---
task: TASK-024
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/70
branch: feature/TASK-024-admin-set-result
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/69 (pre-task cleanup)
commits:
  - 624db68 chore(handoff): take TASK-024 in progress
  - 29e7a5d feat(admin): set_result POST handler + activate Результат tab (conditional + readonly)
  - e7a50cb test(admin): set_result handler (4) + Результат tab visibility (3) = 7 unit
---

# Отчёт по TASK-024: фиксация итога события (вкладка «Результат»)

## Сводка

Закрывает последнюю вкладку карточки события. После Данные/Исходы — Результат: админ выбирает фактический outcome radio-кнопкой, `EventService.set_result` (TASK-009, транзакционный) атомарно ставит `event.result_outcome_id`, `is_archived=true`, `archived_at=now()`, перебирает все прогнозы через `mark_correctness` (UPDATE-CASE). Audit записывается.

Handler — обычный POST с redirect-flash через query-string (та же конвенция, что в categories: `?success=result_set&marked=N` или `?error=already_set`). Доменные исключения покрыты:
- `EventNotFoundError` → 404.
- `EventAlreadyHasResultError` → flash «уже был зафиксирован».
- `OutcomeNotForEventError` → flash «не принадлежит событию».

Вкладка «Результат» условная: видна только при `is_published AND predictions_close_at <= now()`. Иначе `disabled` + `aria-disabled="true"` + tooltip «Доступно после дедлайна приёма прогнозов» (Bootstrap + accessibility-friendly).

Tab content 3 режима:
1. `result_outcome_id != None` → read-only вид с `🏁 Итог: <label>` + `Зафиксирован: dd.mm.yyyy HH:MM UTC`.
2. `len(outcomes) < 2` → warning «нужно минимум 2 исхода, перейдите на Исходы».
3. Иначе → form с radio-кнопками + JS confirm перед submit + «🏁 Зафиксировать».

Server-side trust UI на TASK-024 (как и предлагал task.md): защиты в handler от «архивный event» / «приём ещё не закрыт» нет — server set_result сам бросит соответствующее исключение, если что-то пошло не так. На MVP admin не должен делать запрещённые действия через прямой URL.

## Изменённые файлы

```
* src/admin/routes/events.py                      # +set_result POST handler + импорты
* src/admin/templates/events/form.html            # активирована Результат tab (conditional) + tab content (3 режима)
* tests/unit/admin/test_events_handler.py         # +7 unit тестов (4 handler + 3 visibility)
* handoff/inbox/TASK-024-...md → archive/TASK-024-admin-set-result/task.md
+ handoff/outbox/TASK-024-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    143 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 73 source files
pytest -m "not integration"      211 passed (было 204; +7 events)
pytest tests/integration         109 passed (без регрессий)

CI PR #70 — все 4 job'а зелёные:
  Lint (ruff)                              8s
  Typecheck (mypy)                         19s
  Tests (pytest, unit)                     17s
  Integration                              47s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
make up && make migrate
make admin.create LOGIN=admin PASSWORD="strong!"
make admin

# Browser flow:
# 1) Создать event через UI с predictions_close_at в прошлом, publish.
# 2) Создать 2 исхода через UI (вкладка Исходы из TASK-023).
# 3) В psql: insert prediction какого-то пользователя на этот event/outcome.
# 4) /events/{id}?tab=result → форма с radio + кнопка «🏁 Зафиксировать».
# 5) Submit → confirm → 302 ?success=result_set&marked=1 → зелёный flash.
# 6) Refresh → read-only mode с зафиксированным итогом + archived_at.
# 7) В боте «📋 Мои → Архив» → прогноз с ✅ или ❌ (зависит от outcome).
```

## Что не сделано / вынесено

1. **Server-side guard в `set_result` handler** на `event.is_published AND predictions_close_at <= now()` — спека предложила «опционально, defensive». Я **не добавил** — `EventService.set_result` сам бросит `EventNotFoundError` или сразу выполнит без проверки (если event архивен — `EventAlreadyHasResultError` сработает). Если хочется явный 400 при «приём ещё не закрыт» — отдельной мелкой задачей.
2. **«Отмена фиксации»** — спека «не делать».
3. **Bootstrap modal-confirm** вместо `onclick="return confirm(...)"` — спека «не делать», JS-confirm достаточен.
4. **Email-уведомления админу / бот-уведомления пользователям** — outside scope. Mark_correctness пересчитывает is_correct, бот при следующем `/my → Архив` покажет естественно.

## Открытые вопросы для проектировщика

1. **Server-side guard в handler** — добавлять? Trust UI'ю сейчас. Если admin откроет `/events/{id}?tab=result` для не-опубликованного event'а через прямой URL — form покажется (потому что `result_outcome_id is None and outcomes >= 2` пройдёт), submit отправится → service либо успеет (если в БД условия OK), либо упадёт. На MVP допустимо.
2. **CHECK constraint `ck_event_result_archive_consistency`** (TASK-018) разрешает 3 комбинации: `(no_result, not_archived)`, `(no_result, archived)`, `(has_result, archived)`. Текущий `set_result` ставит все три (result_outcome_id + is_archived + archived_at) одной транзакцией → попадает в третью. CHECK не нарушается.
3. **Refresh после `set_result` redirect** покажет `?tab=result&success=result_set&marked=N` в URL даже после повторных refresh. Это нормально для flash — пока не уйти на другую вкладку. Если хочется чистый URL после первого view — JS `history.replaceState` (overengineering для MVP).
4. **Read-only mode не показывает кнопку «Отмена/Edit»** — что согласовано со спекой «переопределение не предусмотрено в MVP». Если когда-то понадобится — отдельная задача.
5. **Tab disabled через CSS + `aria-disabled`** — Bootstrap class `disabled` стилизует серым, не реагирует на клик. Tooltip показывает причину при наведении. Окей для accessibility?

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-024: фиксация итога события — последняя вкладка карточки. `POST /events/{id}/result` handler в `routes/events.py`: зовёт `EventService.set_result` (TASK-009, транзакционный), маппит `EventAlreadyHasResultError`/`OutcomeNotForEventError`/`EventNotFoundError` на flash-redirect (success+marked / error tags). Активирована вкладка «Результат» в `events/form.html` с условием `is_published AND predictions_close_at <= now()`. Tab content в 3 режимах: read-only (если итог зафиксирован), warning (если <2 исходов), form с radio + JS confirm. 7 новых unit тестов (211 total). PR [#70](https://github.com/nmetluk/gettgbot/pull/70) → squash `9800664`. Pre-task cleanup [#69](https://github.com/nmetluk/bettgbot/pull/69).
```

## Метрики

- Файлов добавлено: 1 (отчёт)
- Файлов изменено: 3 (events.py route, events/form.html, test_events_handler.py)
- Тестов добавлено: 7 (всего 211 unit + 109 integration; было 204+109)
- Время на выполнение: ~30 мин (service всё умеет, только UI + 1 handler + 7 тестов)
