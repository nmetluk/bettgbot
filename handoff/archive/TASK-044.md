---
id: TASK-044
created: 2026-05-26
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/shared/services/dashboard.py
  - handoff/archive/TASK-043-dashboard-counters/
priority: low
estimate: S
---

# TASK-044: Зафиксировать семантику счётчиков на дашборде

## Контекст

В TASK-043 был реализован `DashboardService.get_counters()` — 4 счётчика (users, events, categories, predictions). При ретроспективном ревью обнаружено, что нигде в коде не зафиксировано, **что именно** считается каждым счётчиком:

- `users` через `UserRepository.count_for_admin()` → включает заблокированных (`is_blocked=true`).
- `events` через `EventRepository.count_for_admin(status="all")` → включает черновики и архивные.
- `categories` через `CategoryRepository.count(include_inactive=True)` → активные + неактивные.
- `predictions` через `PredictionRepository.count()` → все, включая по архивным событиям.

Для админа это разумные дефолты (total objects), но без явной фиксации легко поломать при будущем рефакторинге (например, кто-нибудь решит «логично же скрывать удалённых пользователей»).

## Цель

Зафиксировать семантику каждого из 4 счётчиков `DashboardService.get_counters()` в docstring метода. Без изменения поведения.

## Definition of Done

- [ ] В `src/shared/services/dashboard.py` `get_counters()` docstring дополнен явным перечислением «что включено» по каждому ключу.
- [ ] Если для какого-то счётчика семантика не очевидна из имени метода репозитория, в сервисе оставляется однострочный комментарий рядом с вызовом (например, `# включает заблокированных`).
- [ ] Никаких изменений поведения. Существующие 5 тестов (2 unit + 3 integration) остаются зелёными.
- [ ] `ruff check src/shared/services/dashboard.py` чист, `mypy src/shared/services/dashboard.py` без ошибок.
- [ ] PR открыт: `TASK-044: dashboard counters semantics docstring`.
- [ ] Отчёт в `handoff/outbox/TASK-044-report.md`.
- [ ] **🚨 Move-семантика inbox→archive** (см. `handoff/README.md`).
- [ ] **🚨 `make backup` после merge в main**.

## Артефакты

- `* src/shared/services/dashboard.py` — расширенный docstring + inline-комментарии.

## Ссылки

- [`docs/05-admin-spec.md`](../../docs/05-admin-spec.md) — спецификация раздела «Пользователи» и дашборда.
- [`state/DECISIONS.md`](../../state/DECISIONS.md) — запись от 2026-05-26 про sequential awaits.
- [`handoff/archive/TASK-043-dashboard-counters/report.md`](../archive/TASK-043-dashboard-counters/report.md) — исходный фикс.

## Подсказки исполнителю

Минимальный задел — добавить блок Args/Returns/Note в docstring `get_counters()` с явным перечислением. Пример формы (без буквального копирования):

```python
async def get_counters(self) -> dict[str, int]:
    """Счётчики объектов в БД для главной страницы админки.

    Все счётчики возвращают total без фильтров — админу нужна полная
    картина системы, а не «видимое из бота» подмножество.

    Returns:
        dict с ключами:
          - users — все пользователи, включая заблокированных
            (`is_blocked=true`). Удалённых нет — soft-delete не реализован.
          - events — все события, включая черновики (`is_published=false`)
            и архивные (`is_archived=true`).
          - categories — все категории, включая неактивные (`is_active=false`).
          - predictions — все прогнозы, в т.ч. по архивным событиям.

    Note:
        Запросы выполняются последовательно (4 простых COUNT-а). См.
        `state/DECISIONS.md` от 2026-05-26 — concurrent ops на одной
        AsyncSession в SQLAlchemy запрещены.
    """
```

Это документационная задача, не более 15 минут. Тесты на семантику добавлять не нужно — существующих достаточно (они проверяют интерфейс, не семантическую интерпретацию).
