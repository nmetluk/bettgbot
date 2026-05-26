---
id: TASK-033
created: 2026-05-25
author: external-auditor
parallel-safe: false
blockedBy: []
related:
  - docs/audit/2026-05-25-mvp-audit.md
priority: high
estimate: S
---

# TASK-033: Закрыть IDOR в outcomes-CRUD (event_id vs outcome.event_id)

## Контекст

Аудит MVP 2026-05-25, находка **C-01 (Critical, CWE-639 IDOR)**. В `src/admin/routes/outcomes.py` все handler'ы (`update`, `delete`, `edit_form_fragment`) принимают `event_id` и `outcome_id` из URL-пути, но `EventService.update_outcome` / `delete_outcome` (`src/shared/services/event.py:182-201`) фильтруют только по `outcome_id`. Аутентифицированный admin может вызывать `POST /events/1/outcomes/999`, где `999` принадлежит другому событию — мутация пройдёт.

На MVP, где все админы — один человек, эксплуатируемость низкая, но: (а) нарушение атомарности инварианта Event ↔ Outcome; (б) при появлении per-event ролей становится privilege escalation; (в) catastrophic-fix дешевле теперь, чем после доработок.

## Цель

`update_outcome`, `delete_outcome` (и `edit_form_fragment`, который тоже подтягивает outcome) **проверяют, что `outcome.event_id == event_id` из URL**. При несовпадении — `OutcomeNotForEventError` → HTTP 404.

## Definition of Done

- [ ] В `src/shared/exceptions.py` добавлен `class OutcomeNotForEventError(DomainError)` с полями `event_id: int`, `outcome_id: int`.
- [ ] `EventService.update_outcome` принимает **обязательный** kwarg `event_id: int`; в `OutcomeRepository.update(...)` добавлен `where(Outcome.event_id == event_id)`; при 0 затронутых строк → `OutcomeNotForEventError`.
- [ ] Аналогично для `EventService.delete_outcome`.
- [ ] `src/admin/routes/outcomes.py` `update`, `delete`, `edit_form_fragment` передают `event_id` в сервис и обрабатывают `OutcomeNotForEventError` → `HTTPException(404)`.
- [ ] Integration-тесты в `tests/integration/services/test_event_service_admin.py` (или новый файл):
  - `update_outcome` с правильным `event_id` — работает.
  - `update_outcome` с чужим `event_id` — поднимает `OutcomeNotForEventError`.
  - `delete_outcome` — те же два сценария.
- [ ] Unit-тесты в `tests/unit/admin/test_outcomes_handler.py`:
  - POST `/events/1/outcomes/999` где 999 принадлежит event 2 → 404.
- [ ] PR в GitHub, имя `TASK-033: fix IDOR in outcomes CRUD`.
- [ ] Отчёт в `handoff/outbox/TASK-033-report.md`.
- [ ] **🚨 Move-семантика inbox→archive** (см. handoff/README.md).
- [ ] **🚨 `make backup` после merge в main**.

## Артефакты

- `* src/shared/exceptions.py` — новый класс
- `* src/shared/services/event.py` — сигнатуры `update_outcome`/`delete_outcome`
- `* src/shared/repositories/outcome.py` — фильтр `event_id` в update/delete
- `* src/admin/routes/outcomes.py` — проброс `event_id`, обработка нового исключения
- `+ tests/integration/services/test_event_service_admin.py` — два сценария
- `* tests/unit/admin/test_outcomes_handler.py` — тест 404 на чужой outcome

## Ссылки

- Аудит: [`docs/audit/2026-05-25-mvp-audit.md`](../../docs/audit/2026-05-25-mvp-audit.md) — секция C-01
- Конвенция доменных исключений: `docs/08-conventions.md` пункт 7
- CWE: https://cwe.mitre.org/data/definitions/639.html

## Подсказки исполнителю

- Паттерн `reason: Literal[...]` в `OutcomeNotForEventError` не нужен — у исключения единственная причина.
- В handler `delete` уже есть `OutcomeInUseError` — добавь `OutcomeNotForEventError` рядом, реализуй раньше `OutcomeNotFoundError` (поскольку 404 более информативно).
- Не забудь обновить `EventService.add_outcome` — там IDOR не актуален (нет outcome_id в URL), но стиль API должен оставаться единообразным.
