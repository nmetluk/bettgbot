---
id: TASK-024
created: 2026-05-24
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/05-admin-spec.md
  - src/shared/services/event.py (set_result)
  - src/shared/repositories/prediction.py (mark_correctness)
  - src/admin/templates/events/form.html
priority: high
estimate: M
---

# TASK-024: фиксация итога события (вкладка «Результат»)

## Контекст

Четвёртая бизнес-задача в админке и **последняя вокруг события** (после Данные/Исходы — вкладка Результат). Закрывает критический admin-flow: после события админ заходит, выбирает фактический outcome, и **бот** автоматически помечает прогнозы пользователей как «сбылся / не сбылся».

Серверная логика **полностью готова** ([TASK-009](../archive/TASK-009-services)):

- `EventService.set_result(event_id, outcome_id, by_admin_id)` — **транзакционно**:
  - Проверяет `event` существует, `result_outcome_id IS NULL` (нет переопределения).
  - Проверяет `outcome_id` принадлежит этому event'у.
  - Update `event.result_outcome_id`, `event.is_archived = true`, `event.archived_at = now()`.
  - `PredictionRepository.mark_correctness(event_id, correct_outcome_id)` — UPDATE-CASE по всем прогнозам.
  - Audit-log записывается.
  - Возвращает `marked: int` — количество прогнозов, у которых пересчитан `is_correct`.

Доменные исключения готовы:
- `EventNotFoundError`.
- `EventAlreadyHasResultError` — повторная фиксация (защита от двойного нажатия).
- `OutcomeNotForEventError` — исход не принадлежит event'у.

Источники:

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) разделы «События → Вкладка «Результат»»:
  > Видна только когда событие опубликовано и приём прогнозов закрыт (либо `predictions_close_at` прошёл, либо `starts_at` прошёл — на выбор админа).
  > Форма: радио-кнопки со списком `Outcome`, кнопка «Зафиксировать».
  > После подтверждения: редирект на карточку события с зелёным баннером «Итог зафиксирован, N прогнозов проверено».
  > После фиксации поле результата становится read-only. **Переопределение итога не предусмотрено в MVP.**

- [`src/shared/services/event.py`](../../src/shared/services/event.py) — `set_result` готов.
- [`src/admin/templates/events/form.html`](../../src/admin/templates/events/form.html) — там сейчас «Результат (TASK-024)» disabled — активировать.

## Перед стартом — pre-task cleanup PR

В origin/main `2af0550` — last commit (archive TASK-023). **Working tree:**

- `state/PROJECT_STATUS.md` — закрытие TASK-023, новый шаг TASK-024.
- `state/DECISIONS.md` — 1 паттерн (HTMX корневой контейнер).
- `state/BACKLOG.md` — 2 новых пункта тех-долга.
- Новая сессия `sessions/2026-05-24-10-task-023-review/`.
- `handoff/inbox/TASK-024-admin-set-result.md` — эта задача.

Branch: `chore/post-TASK-023-cowork-cleanup`, PR, merge. После — `feature/TASK-024-admin-set-result`.

## Цель

Админ на карточке завершённого опубликованного события выбирает фактический исход radio-кнопкой и нажимает «Зафиксировать». `EventService.set_result` транзакционно обновляет event + все прогнозы. Редирект на карточку события с зелёным flash «Итог зафиксирован, N проверено». После фиксации вкладка «Результат» становится read-only, показывая зафиксированный итог.

Размер M — сервис всё умеет, остался UI + 1 POST handler + 2-3 теста.

## Definition of Done

### Step 1 — Route POST `/events/{event_id}/result`

- [ ] **В `src/admin/routes/events.py`** добавить handler (рядом с publish/unpublish):
  ```python
  @router.post("/{event_id}/result")
  async def set_result(
      request: Request,
      event_id: int,
      outcome_id: int = Form(...),
      admin: AdminUser = Depends(current_admin),
      session: AsyncSession = Depends(_session_dep),
      csrf_protect: CsrfProtect = Depends(),
  ) -> RedirectResponse:
      await csrf_protect.validate_csrf(request)
      try:
          marked = await EventService(session).set_result(
              event_id=event_id, outcome_id=outcome_id, by_admin_id=admin.id,
          )
      except EventNotFoundError:
          raise HTTPException(status_code=404)
      except EventAlreadyHasResultError:
          return RedirectResponse(
              url=f"/events/{event_id}?tab=result&error=already_set",
              status_code=status.HTTP_302_FOUND,
          )
      except OutcomeNotForEventError:
          return RedirectResponse(
              url=f"/events/{event_id}?tab=result&error=outcome_not_for_event",
              status_code=status.HTTP_302_FOUND,
          )
      return RedirectResponse(
          url=f"/events/{event_id}?tab=result&success=result_set&marked={marked}",
          status_code=status.HTTP_302_FOUND,
      )
  ```
- [ ] **Импорт `EventAlreadyHasResultError`, `OutcomeNotForEventError`** в начале файла.

### Step 2 — Расширить `edit_form` поддержкой `tab=result`

- [ ] **В `src/admin/routes/events.py` `edit_form` handler** — уже принимает `tab: str = Query("data")`. Никаких изменений не нужно, кроме того что `events/form.html` теперь рендерит и `tab=result`.

### Step 3 — Расширить `src/admin/templates/events/form.html`

#### 3.1 — Активировать вкладку «Результат»

- [ ] Заменить:
  ```html
  <li class="nav-item">
      <a class="nav-link disabled" href="#">Результат (TASK-024)</a>
  </li>
  ```
  на:
  ```html
  <li class="nav-item">
      {% set _result_enabled = event.is_published and event.predictions_close_at <= now() %}
      <a class="nav-link {% if active_tab == 'result' %}active{% endif %} {% if not _result_enabled %}disabled{% endif %}"
         href="{% if _result_enabled %}/events/{{ event.id }}?tab=result{% else %}#{% endif %}"
         {% if not _result_enabled %}aria-disabled="true" title="Доступно после дедлайна приёма прогнозов"{% endif %}>
          Результат
      </a>
  </li>
  ```
  - Вкладка видна **только** при `is_published AND predictions_close_at <= now()`.
  - При нарушении условия — `disabled` + title-tooltip с объяснением.

#### 3.2 — Добавить tab content `tab=result`

- [ ] **В блок tabs content** (после `tab=data` и `tab=outcomes`):
  ```html
  {% if active_tab == 'result' %}
  <div class="card p-4">
      <h5 class="card-title">Фиксация итога</h5>

      {# Flash messages #}
      {% if request.query_params.get("success") == "result_set" %}
      <div class="alert alert-success">
          ✅ Итог зафиксирован.
          Прогнозов проверено: <strong>{{ request.query_params.get("marked", "?") }}</strong>.
      </div>
      {% endif %}
      {% if request.query_params.get("error") == "already_set" %}
      <div class="alert alert-warning">
          Итог уже был зафиксирован ранее. Переопределение не предусмотрено в MVP.
      </div>
      {% endif %}
      {% if request.query_params.get("error") == "outcome_not_for_event" %}
      <div class="alert alert-danger">
          Выбранный исход не принадлежит этому событию.
      </div>
      {% endif %}

      {% if event.result_outcome_id %}
          {# Read-only mode: итог уже зафиксирован #}
          {% set _result_outcome = (event.outcomes | selectattr('id', 'equalto', event.result_outcome_id) | first) %}
          <p class="lead">
              🏁 Итог: <strong>{{ _result_outcome.label if _result_outcome else '#' + event.result_outcome_id|string }}</strong>
          </p>
          <p class="text-muted">
              Зафиксирован: {{ event.archived_at.strftime('%d.%m.%Y %H:%M') if event.archived_at else '—' }} UTC.
              Переопределение в MVP не предусмотрено.
          </p>
      {% elif event.outcomes | length < 2 %}
          <div class="alert alert-warning">
              Для фиксации итога нужно минимум 2 исхода. Перейдите на вкладку «Исходы».
          </div>
      {% else %}
          {# Form #}
          <form method="post" action="/events/{{ event.id }}/result">
              <input type="hidden" name="csrf_token" value="{{ request.state.csrf_token }}">
              <p class="text-muted">
                  Выберите фактический исход события. После «Зафиксировать» итог записывается в БД,
                  все прогнозы пользователей помечаются «сбылся / не сбылся», событие архивируется.
                  <strong>Переопределение не предусмотрено.</strong>
              </p>
              {% for outcome in event.outcomes %}
              <div class="form-check mb-2">
                  <input class="form-check-input" type="radio" name="outcome_id"
                         id="outcome-{{ outcome.id }}" value="{{ outcome.id }}" required>
                  <label class="form-check-label" for="outcome-{{ outcome.id }}">
                      {{ outcome.label }}
                  </label>
              </div>
              {% endfor %}
              <button type="submit" class="btn btn-success mt-3"
                      onclick="return confirm('Зафиксировать итог? Это действие необратимо.')">
                  🏁 Зафиксировать
              </button>
          </form>
      {% endif %}
  </div>
  {% endif %}
  ```

#### 3.3 — Подгрузить outcomes для tab=result

- [ ] **В `edit_form` handler** убедиться, что `EventService(session).get_event(event_id, with_outcomes=True)` подгружает исходы. **Уже так** — handler передаёт `event` с outcomes. Проверь.

### Step 4 — Защита от GET к /result когда tab не доступен

- [ ] **Не нужно отдельной защиты**: handler `edit_form` принимает любой tab, шаблон сам показывает либо форму, либо read-only вид. Если admin приходит на `?tab=result` для event'а без публикации/дедлайна — увидит **disabled-ссылку на табе** (через CSS) и не сможет на неё кликнуть. Но если **через прямой URL** — то увидит «Для фиксации итога нужно минимум 2 исхода» или сам form (если выполнены условия). Это допустимо: server-side `set_result` сам бросит `EventNotPredictableError` или (например) пройдёт успешно, если условия в БД OK.

  **На MVP** server-side trust UI достаточен — admin не должен делать запрещённые действия. Если хочется строгого guard'а — добавь `if not (event.is_published and event.predictions_close_at <= datetime.now(tz=UTC)): raise HTTPException(status_code=400)` в `set_result` route. **Оставляю на твой выбор**, но рекомендую добавить — defensive.

### Step 5 — Тесты

#### `tests/unit/admin/test_events_handler.py` — расширить

Добавь к существующим тестам:

- [ ] `test_set_result_success_redirects_with_success_flash` — mock `EventService.set_result` → 3, проверить redirect URL `?tab=result&success=result_set&marked=3`.
- [ ] `test_set_result_already_set_redirects_with_error` — service бросает `EventAlreadyHasResultError`, redirect URL `?tab=result&error=already_set`.
- [ ] `test_set_result_outcome_not_for_event_redirects_with_error` — `OutcomeNotForEventError`, redirect `?error=outcome_not_for_event`.
- [ ] `test_set_result_unknown_event_404` — `EventNotFoundError` → 404.
- [ ] `test_edit_form_result_tab_visible_when_published_and_deadline_passed` — рендер шаблона с условиями (mock event с `is_published=True`, `predictions_close_at < now`).
- [ ] `test_edit_form_result_tab_disabled_when_not_published` — рендер с `is_published=False`.
- [ ] `test_edit_form_result_tab_shows_readonly_when_result_set` — `result_outcome_id != None`, шаблон рендерит read-only вид с itm.label.

#### Существующие integration-тесты `EventService.set_result` уже в TASK-009

Не дублируем. См. `tests/integration/services/test_event_service.py` (или подобный).

### Качество и workflow

- [ ] `uv run mypy src/shared src/bot src/admin` — зелёный.
- [ ] `uv run ruff check src tests`, `uv run ruff format --check src tests` — зелёные.
- [ ] `uv run pytest -m "not integration"` — все unit, включая ~7 новых.
- [ ] `uv run pytest tests/integration -m integration` — без падений.
- [ ] CI на PR — все четыре job'а зелёные.
- [ ] **Ручная проверка (опц., не в DoD):**
  - Создать event через admin UI с `predictions_close_at` в прошлом, опубликовать.
  - Создать 2 исхода через UI.
  - Сделать прогноз через бот (или в psql).
  - В админке: открыть карточку event → вкладка «Результат» активна.
  - Radio-выбор → «Зафиксировать» → confirm → success-flash «Итог зафиксирован, 1 проверено».
  - Обновить страницу → вкладка показывает read-only mode с итогом.
  - В боте «📋 Мои прогнозы → Архив» → прогноз показан с ✅ или ❌.
- [ ] Ветка `feature/TASK-024-admin-set-result`, Conventional Commits:
  - `feat(admin): POST /events/{id}/result + flash success/error`
  - `feat(admin): activate Результат tab + readonly mode + condition (published+deadline_passed)`
  - `test(admin): set_result handler + result tab visibility (7 unit)`
- [ ] PR в `main`, отчёт `handoff/outbox/TASK-024-report.md`, задача → `handoff/archive/TASK-024-admin-set-result/task.md`.

## Артефакты

```
* src/admin/routes/events.py                      # +set_result POST handler
* src/admin/templates/events/form.html            # activate Результат tab + content
* tests/unit/admin/test_events_handler.py         # +7 unit тестов
```

## Ссылки

- [docs/05-admin-spec.md](../../docs/05-admin-spec.md) — раздел «События → Вкладка «Результат»»
- [src/shared/services/event.py](../../src/shared/services/event.py) — `set_result` транзакционный (готов)
- [src/shared/repositories/prediction.py](../../src/shared/repositories/prediction.py) — `mark_correctness` (готов)
- [src/admin/templates/events/form.html](../../src/admin/templates/events/form.html) — там disabled-ссылка на Результат, активировать

## Подсказки исполнителю

- **`set_result` транзакционен** — всё или ничего. Если `mark_correctness` падает после `set_result` (теоретически — например, FK-conflict), вся транзакция откатывается, event остаётся не-архивным. На MVP — никакой компенсации не нужно.
- **`event.outcomes | selectattr('id', 'equalto', X) | first`** в Jinja — стандартный фильтр для поиска по списку.
- **`onclick="return confirm(...)"`** на кнопке submit — простейший JS-confirm перед POST. Альтернатива (Bootstrap modal) — переусложнение для MVP. `hx-confirm` тоже работает, но эта форма не HTMX — обычный POST с redirect.
- **Disabled-tab CSS**: Bootstrap class `disabled` для `<a class="nav-link disabled">` рендерит ссылку серой и не реагирует на клик. `aria-disabled="true"` + `title=` для tooltip — accessibility-friendly.
- **`request.query_params.get("marked", "?")`** — fallback на `"?"` если параметр отсутствует. Маловероятно (handler всегда его передаёт), но defensive.
- **`now()` в Jinja** — глобал из TASK-022. Используется в условии видимости таб.
- **`event.predictions_close_at <= now()`** — equality для случая «дедлайн ровно сейчас» (открыто? закрыто?). По спеке `docs/04` — дедлайн закрывает приём; запись с `==` тоже считаем закрытой.

## Что НЕ делать

- **Не делать переопределение итога** — спека явно «не предусмотрено в MVP». Read-only после фиксации.
- **Не добавлять HTMX inline-fix** — обычный POST с redirect.
- **Не предупреждать пользователей бота** о фиксации итога — `mark_correctness` пересчитывает `is_correct`, бот при следующем `/my → Архив` покажет это естественно.
- **Не уведомлять админа email'ом** — outside scope.
- **Не добавлять «отмену фиксации»** — outside scope, безопаснее не делать.
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` за пределами стандартного pre-task cleanup PR.
- Не зеркалить в Drive вручную.
