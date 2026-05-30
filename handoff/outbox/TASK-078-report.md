---
task: TASK-078
completed: 2026-05-30
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/136
branch: feature/TASK-078-restore-event-detail-test
commits:
  - 687cef8 feat(handoff): TASK-078 — restore event detail integration regression test
  - 84d6618 fix(handoff): TASK-078 — use httpx.AsyncClient + ASGITransport for event loop safety
---

# Отчёт по TASK-078: вернуть рабочую интеграционную регрессию на GET /events/{id}

## Сводка

Восстановлен интеграционный тест `tests/integration/services/test_event_detail_admin.py` (удалённый в TASK-076).
Исправлен дефект харнесса: синхронный `TestClient` заменён на `httpx.AsyncClient` + `ASGITransport`,
что решило проблему "Event loop is closed" при совместном прогоне тестов.

Все 4 тест-кейса проходят в СОВМЕСТНОМ прогоне `pytest tests/integration -m integration`:
- черновик без исходов (главный регресс на MissingGreenlet);
- опубликованное событие с ≥2 исходами;
- вкладка `?tab=result` у закрытого события;
- 404 на несуществующий id.

## Изменённые файлы

```
* tests/integration/services/test_event_detail_admin.py  # восстановлен с httpx.AsyncClient
+ handoff/archive/TASK-078-restore-event-detail-test/TASK-078.md
+ handoff/outbox/TASK-078-report.md
```

## Как воспроизвести / запустить

```bash
# все интеграционные тесты (совместный прогон)
uv run pytest tests/integration -m integration -v

# только этот файл
uv run pytest tests/integration/services/test_event_detail_admin.py -v
```

## Фактический вывод combined-прогона

```
tests/integration/services/test_event_detail_admin.py ....               [ 49%]
======================== 167 passed in 66.90s (0:01:06) ========================
```

## Что не сделано

Ничего — все требования задачи выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-30 — TASK-078: восстановлена интеграционная регрессия на GET /events/{id}, исправлен event loop харнесс (PR #136)
```
