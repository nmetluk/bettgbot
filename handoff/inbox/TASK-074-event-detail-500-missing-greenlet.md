---
id: TASK-074
created: 2026-05-30
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/routes/events.py
  - src/shared/repositories/event.py
  - src/shared/services/event.py
  - src/admin/templates/events/form.html
priority: high
estimate: S
---

# TASK-074: 500 при открытии/создании события (lazy-load relationship в синхронном рендере)

## Симптом (от владельца)

- Создание тестового события → **Internal Server Error**, но событие появляется в списке.
- Открыть существующее событие на редактирование → тоже **500**.

## Корневая причина (диагностика архитектора)

Оба сценария упираются в один GET-вью `GET /events/{id}` (`edit_form`), т.к. `create_event`
после успешного INSERT делает `RedirectResponse` на `/events/{event.id}`.

`edit_form` грузит событие через `EventService.get_event(event_id, with_outcomes=True)` →
`EventRepository.get_with_outcomes`, который делает **только** `selectinload(Event.outcomes)`:

```python
stmt = select(Event).options(selectinload(Event.outcomes)).where(Event.id == event_id)
```

А редизайненный шаблон `events/form.html` обращается к ленивым relationship'ам, которые
**не загружены**:
- `event.category.name` (page-sub и нигде не eager-load для деталей),
- `event.created_by_admin.username` (карточка «Состояние»).

Jinja рендерит **синхронно, вне greenlet/await-контекста**. Доступ к незагруженному
relationship в async-SQLAlchemy в этот момент кидает
`sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here`
→ необработанное исключение → **500**.

Почему **список** работает (и событие там видно): `list_admin_with_counts` явно делает
`selectinload(Event.category)` (см. `repositories/event.py`), а INSERT в `create_event`
проходит до редиректа — данные сохраняются. 500 ловит только страница деталей.

Почему дизайн-аудит не поймал: в `docs/audit/2026-05-30-design-audit.md` проверяли **списки**
`/events`/`/users`, страницу деталей события не открывали.

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-074-report.md`.
> 🚨 Не закрыто, пока CI зелёный и PR смёржен.

- [ ] Для вью деталей/редактирования события eager-load'ить **все** relationship'ы, к которым
      обращается `form.html`: как минимум `Event.category` и `Event.created_by_admin`
      (в дополнение к `Event.outcomes`). Грузить через `selectinload` (joinedload не нужен).
      Реализовать в слое репозитория/сервиса (бизнес-логику в роут не выносить — конвенция).
      Предпочтительно отдельный метод (напр. `get_for_admin_detail(event_id)`), либо
      параметризовать существующий, не сломав других потребителей `get_with_outcomes`
      (его использует `set_result` и т.п. — там category/admin не нужны, лишний JOIN не тащить).
- [ ] Защититься на будущее: на странице деталей не должно быть ни одного обращения к
      незагруженному relationship. Перепроверить шаблон `form.html` на предмет других
      ленивых обращений (`event.result_outcome`, `outcome.predictions` в табе «Результат» —
      `outcome.predictions` это relationship! Под `_result_enabled`/result-таб может стрельнуть
      тем же MissingGreenlet. Загрузить или заменить на агрегат).
- [ ] **Тест-регрессия (обязательно):** интеграционный тест, который реально рендерит
      `GET /events/{id}` для свежесозданного **черновика без исходов** и ожидает **200**, а не 500.
      Именно этот кейс (draft, 0 outcomes, есть category + автор) воспроизводит баг.
      Желательно отдельный кейс на опубликованное событие и на таб `?tab=result`.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные; PR `TASK-074: fix 500 on event detail (eager-load relationships)`;
      CI зелёный; PR смёржен; локальная `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Сопутствующие дефекты (по коду `events.py`) — оценить, чинить по решению исполнителя

1. **naive datetime vs aware-UTC конвенция (TASK-067).** `_parse_dt` возвращает
   `datetime.fromisoformat(raw)` — **naive**, но проект требует aware-UTC
   (`src/shared/time.py`: «Запрещено naive datetime»). На вход в timestamptz-колонку идёт naive.
   Привести к aware UTC (`.replace(tzinfo=UTC)`) на границе парсинга формы. Если это меняет
   поведение — отметить в отчёте, не тащить скрытно.
2. **CHECK `ck_event_close_before_start` → 500.** В модели есть constraint
   `predictions_close_at <= starts_at`. `create_event`/`update_event` не валидируют это на уровне
   приложения → при «дедлайн позже старта» прилетит `IntegrityError` → 500 вместо понятной
   ошибки формы. Добавить валидацию с дружелюбным сообщением (как `_render_form_with_error`).
3. **`create_event` ловит только `EventInvalidContentError`.** Любая другая доменная/інтегрити
   ошибка не обработана. Сузить try до вызова сервиса и покрыть ожидаемые ошибки.

Пункты 2–3 можно вынести в отдельный тикет, если раздувают объём — отметить в отчёте.

## Вне скоупа

- Редизайн формы и отступы — отдельный тикет TASK-075.

## Артефакты

- `* src/shared/repositories/event.py` — eager-load category/created_by_admin (и predictions-агрегат для result-таба)
- `* src/shared/services/event.py` — метод-обёртка для admin-detail
- `* src/admin/routes/events.py` — использовать новый метод; (опц.) валидация дат/ошибок
- `* tests/integration/...` — регрессия на 200 для draft-события
- `* handoff/outbox/TASK-074-report.md`

## Ссылки

- `src/admin/templates/events/form.html` — обращения `event.category.name`, `event.created_by_admin.username`, `outcome.predictions`
- `src/shared/repositories/event.py` — `get_with_outcomes` (узкий selectinload) vs `list_admin_with_counts` (грузит category)
