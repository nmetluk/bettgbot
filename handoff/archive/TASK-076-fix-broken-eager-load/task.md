---
id: TASK-076
created: 2026-05-30
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/shared/repositories/event.py
  - handoff/archive/TASK-074-event-detail-500-missing-greenlet
  - handoff/outbox/TASK-074-report.md
  - tests/integration/services/test_event_detail_admin.py
  - .github/workflows/ci.yml
priority: high
estimate: XS
---

# TASK-076: 500 на деталях события всё ещё жив — строковая loader-опция в TASK-074 (ArgumentError)

## Что не так

TASK-074 закрыт и смёржен (PR #129, commit `d03a4f2`), но **баг не исправлен** — заменил один
500 на другой. В `EventRepository.get_for_admin_detail` (origin/main HEAD) стоит:

```python
selectinload(Event.outcomes).selectinload("predictions"),  # type: ignore[arg-type]
```

Строковая форма loader-опции **удалена в SQLAlchemy 2.0** (проект на `sqlalchemy>=2.0,<3`).
Проверено на SA 2.0.50: `selectinload(X).selectinload("predictions")` кидает
`sqlalchemy.exc.ArgumentError: Strings are not accepted for attribute names in loader options;
please use class-bound attributes directly` — **в момент построения запроса**, до обращения к БД,
безусловно (не зависит от моделей). То есть `get_for_admin_detail` падает при каждом вызове →
`GET /events/{id}` (создание + редактирование) по-прежнему отдаёт **500**.

`# type: ignore[arg-type]` — это и был сигнал: mypy ругался на нетипизированный аргумент, его
заглушили вместо того, чтобы исправить.

## Почему CI это пропустил (отдельно проверить — процессная дыра)

Интеграционный тест `test_event_detail_admin.py` реально дергает `GET /events/{id}` и при живом
баге обязан падать (500 ≠ 200). CI-джоба `integration` (`pytest tests/integration -m integration`)
гоняется против реального postgres:16. Значит одно из двух, и это нужно закрыть:
- джоба `integration` **не блокирует** merge (не в required checks branch protection), **или**
- тест по какой-то причине не выполнился/заскипан в CI.

В отчёте TASK-074 заявлен «зелёный CI» — фактически фикс не проходит честный интеграционный прогон.
Это уже второй случай расхождения отчёта с реальностью (ср. TASK-071: завышенные числа контраста).

## Definition of Done

> 🚨 Перед `chore(handoff): archive` — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-076-report.md`.
> 🚨 Не закрыто, пока CI зелёный и PR смёржен.

- [ ] Заменить строку на **class-bound** атрибут (`Outcome.predictions` существует, см.
      `src/shared/models/outcome.py:31`), импортировав `Outcome`:
      ```python
      from src.shared.models import Event, Outcome  # уже есть Event
      ...
      selectinload(Event.outcomes).selectinload(Outcome.predictions),
      ```
      Снять `# type: ignore[arg-type]` — с class-bound атрибутом mypy не ругается. Если `ignore`
      остаётся нужен — значит что-то ещё не так, разобраться, а не глушить.
- [ ] **Подтвердить, что тест реально ловит баг:** на ТЕКУЩЕМ (сломанном) коде интеграционные
      тесты `test_event_detail_admin.py` должны падать (200 ≠ ArgumentError→500); после правки —
      проходить. Прогнать локально против реального Postgres (`pytest tests/integration -m integration`),
      привести вывод в отчёт. Не «CI зелёный» на словах — приложить фактический прогон.
- [ ] **Закрыть процессную дыру CI:** убедиться, что джоба `integration` входит в required checks
      для merge в `main` (branch protection). Если нет — это причина, по которой TASK-074 уехал
      сломанным. Если поправить protection нельзя из задачи — явно вынести в отчёт для владельца.
- [ ] (опц., на усмотрение) `outcome.predictions|length` тащит ВСЕ строки прогнозов ради счётчика.
      Если прогнозов много — это N селектов и лишняя память. Рассмотреть агрегат-counts вместо
      загрузки коллекции (как сделано для списка в `list_admin_with_counts`). Не блокер; если
      выносится — отметить.
- [ ] `ruff`/`mypy src/shared`/`pytest` зелёные; PR `TASK-076: fix broken eager-load (class-bound loader option)`;
      CI зелёный (с РЕАЛЬНО выполненной интеграцией); PR смёржен; локальная `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Артефакты

- `* src/shared/repositories/event.py` — class-bound `selectinload(Outcome.predictions)`
- `* (если правится) .github/workflows/ci.yml` / branch protection — integration в required
- `* handoff/outbox/TASK-076-report.md`

## Ссылки

- Сломанная строка: `src/shared/repositories/event.py` → `get_for_admin_detail`
- Доказательство: SA 2.0.50, `selectinload(X).selectinload("predictions")` → `ArgumentError` при построении
- `src/shared/models/outcome.py:31` — `predictions: Mapped[list[Prediction]] = relationship(...)`
