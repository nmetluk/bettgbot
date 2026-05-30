---
task: TASK-078
type: amendment
created: 2026-05-30
author: cowork-agent
re: PR #136 не влит — 2/4 теста падают при совместном прогоне
---

# Амендмент к TASK-078: задача НЕ закрыта — почини event-loop, тесты должны проходить вместе

## Факт (проверено архитектором против origin/main)

`main` HEAD = `383331c` (это публикация дока TASK-078, PR #135 — он влился). А **PR #136 НЕ влит**:
файла `tests/integration/services/test_event_detail_admin.py` на `main` нет. Гейт корректно блокирует
#136, потому что в отчёте сам же указан дефект: «при совместном запуске 2 из 4 падают
`RuntimeError: Event loop is closed`». CI гоняет `pytest tests/integration -m integration` —
**совместно**. Значит integration-джоба красная → merge заблокирован. Это не «готово».

## Это дефект, а не «известная проблема»

`RuntimeError: Event loop is closed` здесь — следствие смешения **синхронного `TestClient`** (он
поднимает и затем закрывает собственный event loop через anyio-portal) с async-фикстурами и
модульным loop'ом pytest-asyncio. После первого теста loop закрыт → следующие async-операции на нём
падают. Нельзя ни скипать, ни `xfail`, ни запускать тесты по одному, ни удалять — это маскировка.

## Как чинить (рекомендация)

Убрать синхронный `TestClient`, гонять ASGI-приложение на **том же** loop'е через `httpx.AsyncClient`
+ `ASGITransport` — тогда конкурирующего loop'а нет:

```python
import httpx
from httpx import ASGITransport
from src.admin.app import app
from src.admin.deps import current_admin

app.dependency_overrides[current_admin] = lambda: admin   # admin — реальный AdminUser из БД
try:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/events/{event.id}")
    assert resp.status_code == 200
finally:
    app.dependency_overrides.clear()
```

Все 4 кейса — async, на одном loop'е, без `TestClient`. Если `httpx` ещё не в dev-зависимостях —
добавить (он почти наверняка уже тянется FastAPI/Starlette).

## Definition of Done (дополнение)

- [ ] Все 4 кейса проходят **в совместном прогоне** `pytest tests/integration -m integration` —
      не изолированно. Приложить фактический вывод combined-прогона в отчёт.
- [ ] Никаких `xfail`/`skip`/`-p no:randomly`/«запускать по одному» как обхода loop-проблемы.
- [ ] PR #136 (или новый) **сам** влился auto-merge'ем по зелёному CI; тест присутствует на `main`.
- [ ] Снять статус blocked/in-progress корректно; отчёт + archive; inbox чист
      (в т.ч. убрать сам TASK-078-док из inbox в archive по обычному циклу).

## Вне скоупа — без изменений

Код `get_for_admin_detail` не трогать (он верный после TASK-076). Только тест и его харнесс.
