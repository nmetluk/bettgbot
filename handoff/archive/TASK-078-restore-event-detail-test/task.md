---
id: TASK-078
created: 2026-05-30
author: cowork-agent
parallel-safe: true
blockedBy: []
related:
  - src/admin/routes/events.py
  - src/admin/deps.py
  - tests/unit/admin/test_events_handler.py
  - handoff/archive/TASK-076-fix-broken-eager-load-string-loader
priority: high
estimate: S
---

# TASK-078: вернуть рабочую интеграционную регрессию на `GET /events/{id}` (удалена в TASK-076)

## Контекст

Фикс TASK-076 на `main` **корректен** (`repositories/event.py:53` →
`selectinload(Event.outcomes).selectinload(Outcome.predictions)`, `Outcome` импортирован).
Но при этом исполнитель **удалил** регрессионный тест `tests/integration/services/test_event_detail_admin.py`,
сославшись на «auth issues с FastAPI TestClient». В итоге сейчас `GET /events/{id}` не покрыт ни одной
интеграционной проверкой — остались только unit с моками, которые этот класс багов
(MissingGreenlet / неверная loader-опция) **не ловят**, т.к. они проявляются только при реальном
async-DB + рендере шаблона.

Это тот самый 500, который мы чинили дважды (TASK-074 → TASK-076) и который владелец видел в браузере.
Оставлять его без регрессии нельзя — иначе следующий рефактор `get_for_admin_detail`/шаблона снова
протащит 500, и гейт его не остановит.

## Почему «auth issue» — это чинится, а не повод удалять

Удалённый тест подделывал session-cookie с `secret="test-secret"`, который не совпадает с боевым
секретом проверки → запрос редиректился на логин, не доходя до `edit_form`. Правильный путь —
**не подделывать cookie, а переопределить зависимость аутентификации**, как уже сделано в unit-тестах
хендлеров (`tests/unit/admin/test_events_handler.py` и др. используют паттерн с подменой `current_admin`):

```python
from src.admin.deps import current_admin
app.dependency_overrides[current_admin] = lambda: admin   # admin — реальный AdminUser из БД
# ... TestClient(app) ...
# в finally: app.dependency_overrides.clear()
```

Тогда запрос доходит до роута и реально дёргает `get_for_admin_detail` против настоящего Postgres.

## Definition of Done

> 🚨 НЕ удалять тест ради зелёного CI. Если тест падает — чинить причину (харнесс или код), а не тест.
> 🚨 Перед archive — ОБЯЗАТЕЛЬНО `handoff/outbox/TASK-078-report.md`. Не закрыто, пока CI зелёный и PR смёржен.

- [ ] Восстановить интеграционный тест `tests/integration/services/test_event_detail_admin.py`
      (можно взять из истории: `git show <commit-до-удаления>:tests/integration/services/test_event_detail_admin.py`),
      переведя аутентификацию на `app.dependency_overrides[current_admin]` (паттерн из unit-тестов).
- [ ] Кейсы, каждый ждёт **200** (не 302, не 500):
      - черновик без исходов (`is_published=False`, 0 outcomes) — главный кейс исходного 500;
      - опубликованное событие с ≥2 исходами;
      - таб `?tab=result` у закрытого опубликованного события (там `outcome.predictions` — relationship,
        тоже должен быть eager-load'ен).
      Плюс существующий кейс 404 на несуществующий id.
- [ ] Тест должен **реально падать на коде до TASK-076** (sanity: если временно вернуть строковую
      loader-опцию — тест краснеет). Это подтверждает, что он ловит баг, а не проходит вхолостую.
      Достаточно описать проверку в отчёте, возвращать баг в main не нужно.
- [ ] Прогнать локально против реального Postgres (`pytest tests/integration -m integration -k event_detail`),
      приложить **фактический вывод** в отчёт (не «CI зелёный» на словах).
- [ ] `ruff`/`mypy`/`pytest` зелёные; PR через обычный флоу с `gh pr merge --auto --squash`;
      влиться должен **сам** по зелёному CI (это и есть проверка гейта); локальная `main` синхронизирована.
- [ ] Отчёт + archive; inbox чист.

## Вне скоупа

- Менять код `get_for_admin_detail` (он уже верный) — только тест.
- Общий рефактор харнесса интеграционных тестов — если всплывёт, отдельным тикетом.

## Артефакты

- `* tests/integration/services/test_event_detail_admin.py` — восстановить с auth через dependency override
- `* (возм.) tests/integration/conftest.py` — хелпер authed-client, если удобно переиспользовать
- `* handoff/outbox/TASK-078-report.md`

## Ссылки

- Удаление теста: коммит `cecb539` (TASK-076, PR #134) — `git show cecb539 -- tests/integration/services/test_event_detail_admin.py`
- Паттерн auth-override: `tests/unit/admin/test_events_handler.py`
- Первопричина 500: `repositories/event.py` `get_for_admin_detail` + шаблон `events/form.html`
