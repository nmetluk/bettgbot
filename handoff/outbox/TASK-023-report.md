---
task: TASK-023
completed: 2026-05-24
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/67
branch: feature/TASK-023-admin-outcomes
related-prs:
  - https://github.com/nmetluk/bettgbot/pull/66 (pre-task cleanup)
commits:
  - 6427aac chore(handoff): take TASK-023 in progress
  - a2fffba feat(admin): outcomes HTMX CRUD routes + _list/_form partials + activate Исходы tab
  - 1e07d8a test(admin): outcomes handler tests (10 unit)
---

# Отчёт по TASK-023: CRUD исходов через HTMX inline-edit

## Сводка

Первая HTMX-задача в админке. Вкладка «Исходы» в карточке события теперь работает inline: список загружается через `hx-trigger="load"`, добавление/редактирование/удаление через `hx-post` + `hx-swap="outerHTML"` на корневой `<div id="outcomes-container">` — каждый fragment начинается с того же контейнера, HTMX полностью заменяет блок без вложенных wrap'еров.

Сервисный слой полностью переиспользован из TASK-009: `EventService.add_outcome`, `update_outcome`, `delete_outcome` уже с audit и `OutcomeInUseError` (FK RESTRICT от Prediction). Handler-слой только обвязка + рендер фрагментов.

`_list_response(request, session, event_id, error=None, status_code=200)` — helper, который write-handler'ы зовут после операции для re-fetch + render. Чистый DRY: 4 из 6 handler'ов используют его.

Активирована вкладка «Исходы» в `events/form.html` (была disabled-link «Исходы (TASK-023)»). Контент вкладки — div с spinner и `hx-get` на `/events/{id}/outcomes` с `hx-trigger="load"` — fragment подтягивается при открытии.

CSRF в HTMX-формах через `<input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">`. `CsrfTokenMiddleware` (TASK-022) покрывает все GET, токен на момент рендера fragment свежий.

`hx-confirm` (window.confirm) для delete-button — достаточно для MVP, JS-modal'ы переусложнение.

## Изменённые файлы

```
+ src/admin/routes/outcomes.py                    # 6 HTMX handlers + _list_response helper
+ src/admin/templates/outcomes/_list.html         # fragment списка с add-кнопкой
+ src/admin/templates/outcomes/_form.html         # fragment add/edit shared
* src/admin/templates/events/form.html            # активирована Исходы tab + hx-trigger=load
* src/admin/app.py                                # +include_router(outcomes_routes.router)
* tests/unit/admin/test_events_handler.py         # обновлён assert (вкладка теперь без "(TASK-023)")
+ tests/unit/admin/test_outcomes_handler.py       # 10 unit тестов
* handoff/inbox/TASK-023-...md → archive/TASK-023-admin-outcomes/task.md
+ handoff/outbox/TASK-023-report.md
```

## Тесты и CI

```
ruff check src tests             All checks passed!
ruff format --check src tests    143 files already formatted
mypy src/shared src/bot src/admin   Success: no issues found in 73 source files
pytest -m "not integration"      204 passed (было 194; +10 outcomes)
pytest tests/integration         109 passed (без регрессий, новых integration нет —
                                  add/update/delete_outcome уже покрыты в TASK-009)

CI PR #67 — все 4 job'а зелёные:
  Lint (ruff)                              11s
  Typecheck (mypy)                         20s
  Tests (pytest, unit)                     18s
  Integration                              51s
```

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
make up && make migrate
make admin.create LOGIN=admin PASSWORD="strong!"
make admin

# Browser flow:
# 1) Login → /events/new → создать событие → Save
# 2) /events/{id}?tab=outcomes → spinner → list fragment («Исходов ещё нет»)
# 3) «Добавить исход» → inline-форма → submit → исход в списке
# 4) Повторить ещё раз (нужно ≥2 для publish)
# 5) «Изм.» → inline-edit → submit → label обновлён
# 6) «Trash» → confirm dialog → удалено
# 7) В psql: insert Prediction на этот outcome
# 8) Trash повторно → 409 alert «нельзя удалить, есть прогнозы»
# 9) tab=data → Publish → 200 (≥2 outcomes — publish работает)
```

## Что не сделано / вынесено

1. **Drag-drop sort_order** — спека явно «не делать», number-input достаточно.
2. **Bootstrap modal-confirm** вместо `hx-confirm` — спека «не делать», window.confirm покрывает MVP.
3. **Pagination исходов** — 2-5 на событие, не нужна.
4. **Вкладка «Результат»** — disabled-link, это TASK-024.
5. **`update_outcome` / `delete_outcome` НЕ raise `OutcomeNotFoundError`** при несуществующем outcome_id — service сейчас просто no-op (UPDATE/DELETE WHERE id=X without affected rows). Мои handler'ы `except OutcomeNotFoundError` — dead code, оставлен для resilience. Если хотим строгий 404 → расширить service. Записываю как открытый вопрос.
6. **`add_outcome` не делает re-fetch внутри handler** — `_list_response` сам делает get_event. 2 SQL на write: action + select. На admin (~5 outcomes per event) — приемлемо.

## Открытые вопросы для проектировщика

1. **`update_outcome` / `delete_outcome` без NotFound** — если фронт отправит `outcome_id=99999`, service выполнит no-op (UPDATE/DELETE WHERE returning 0 rows). Handler возвращает обновлённый list — выглядит как успех. Хотим строгий 404? Тогда нужно в service: `existing = await self._outcomes.get_by_id(outcome_id); if existing is None: raise OutcomeNotFoundError`. Микро-overhead +1 SELECT на write.
2. **HTMX-pattern с корневым `#outcomes-container` + `hx-swap="outerHTML"`** — выбрал потому что fragment контролирует свой собственный wrap. Альтернатива (`hx-swap="innerHTML"` на внешнем контейнере) — fragment был бы plain `<ol>`+`<button>` без wrap, контейнер всегда вокруг. Текущий вариант делает fragment-rendering симметричным («каждый fragment самодостаточный»), но требует, чтобы `outerHTML` не сломал родительский layout. Согласуем как convention для TASK-024+?
3. **`add_outcome` не валидирует `event.is_archived`** — если event архивный, добавить исход всё равно даёт SQL OK. Не критично (UI не покажет кнопку для архивного event'а после публикации, но через прямой URL можно). Service-level guard?
4. **CSRF token из middleware на момент рендера fragment** — токен генерируется на GET form-fragment, потом POST verify проходит. Если admin откроет fragment в 1 окне, в 2-м окне сделает logout (новая сессия / regenerated CSRF cookie), потом submit fragment из 1-го — 403. Это нормальный security trade-off, окей?
5. **`OutcomeInUseError`-409 возвращает `_list.html`** с alert. Альтернатива — отдельный partial `_error.html`. Сейчас alert внутри list-fragment — пользователь видит и список (актуальный), и alert. OK?
6. **HTMX 2.x работает с CDN** (TASK-019). Если production когда-то нужен offline — отдельной задачей переходим на self-hosted.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-24 — TASK-023: CRUD исходов через HTMX inline-edit — первая HTMX-задача в админке. 6 handler'ов в `src/admin/routes/outcomes.py` (list/new/create/edit/update/delete fragments) + `_list_response` helper для DRY. 2 partials (`_list.html` + `_form.html`) с корневым `<div id="outcomes-container">` для `hx-swap="outerHTML"`. Активирована вкладка «Исходы» в `events/form.html` через `hx-trigger="load"` со spinner-placeholder'ом. CSRF в HTMX-формах через `request.state.csrf_token` (middleware из TASK-022). 10 новых unit тестов (204 total). Сервисный слой TASK-009 полностью переиспользован. PR [#67](https://github.com/nmetluk/bettgbot/pull/67) → squash `97725c7`. Pre-task cleanup [#66](https://github.com/nmetluk/bettgbot/pull/66).
```

## Метрики

- Файлов добавлено: 4 (outcomes route + 2 partials + 1 test + report)
- Файлов изменено: 3 (app, events/form.html, test_events_handler)
- Тестов добавлено: 10 (всего 204 unit + 109 integration; было 194+109)
- Время на выполнение: ~30 мин (компактная задача — service готов, HTMX-обвязка прямолинейная)
