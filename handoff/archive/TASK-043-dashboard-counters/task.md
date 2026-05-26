---
id: TASK-043
created: 2026-05-26
author: owner
parallel-safe: true
blockedBy: []
related:
  - state/PROJECT_STATUS.md
  - src/admin/routes/dashboard.py
priority: high
estimate: S
---

# TASK-043: Реализовать счётчики на дашборде админки

## Контекст

После выкладки MVP на прод VPS обнаружено, что главная страница админки (`/`) показывает пустой дашборд — все счётчики равны 0.

Причина: в TASK-019 (2026-05-24) был создан dashboard-роут с **заглушкой** и комментарием `"""Dashboard route — заглушка. Реальные счётчики — после TASK-024+."""`. Однако в последующих задачах (TASK-024..TASK-032) реализация счётчиков так и не была выполнена — либо просмотрели, либо интерпретировали "после TASK-024+" как "когда-нибудь потом".

Проект уже в проде, и это создаёт плохое впечатление для владельца.

**Связанные репозитории** (частично готовы, имеют `list_*` методы с aggregations):
- `src/shared/repositories/user.py` — есть `list_for_admin_with_prediction_counts`
- `src/shared/repositories/event.py` — есть `list_for_admin_with_predictions_count`
- `src/shared/repositories/category.py` — есть `list_with_event_counts`
- `src/shared/repositories/prediction.py` — базовый CRUD

## Цель

Заменить хардкод нулей в `dashboard.py` на реальные значения из БД.

## Definition of Done

- [] Добавлен метод `count()` в каждый из 4 репозиториев (или использован существующий `list_*` если эффективнее)
- [] `DashboardService` (или прямой вызов репозиториев в handler'е) возвращает реальный dict `{users, events, categories, predictions}`
- [] Шаблон `dashboard.html` обновлён — удалена строка `⚠️ Реальные счётчики подключатся в TASK-024+.`
- [] Добавлены 2-3 unit-теста на счётчики (repository-level) или 1 integration на сам dashboard-handler
- [] `ruff check` чист, `mypy` без ошибок
- [ ] PR открыт: `TASK-043: implement dashboard counters`
- [ ] Исходная задача перемещена в `handoff/archive/`
- [ ] **🚨 `make backup` после merge**

## Артефакты

- `* src/shared/repositories/{user,event,category,prediction}.py` — добавить `count()` или использовать существующие методы
- `* src/shared/services/dashboard.py` — новый (опционально, если нужен сервис)
- `* src/admin/routes/dashboard.py` — заменить хардкод на вызов БД
- `* src/admin/templates/dashboard.html` — убрать warning-текст
- `* tests/unit/test_dashboard_counters.py` или `tests/integration/test_dashboard_route.py` — новый

## Подсказки исполнителю

1. **Выбор подхода:** для 4 простых `COUNT(*)` запросов допустимо вызвать репозитории напрямую из handler'а (без отдельного сервиса). Либо создать минимальный `DashboardService` — на усмотрение исполнителя. Учитывая существующий паттерн проекта (сервисы есть для всех доменов), предпочтительно создать сервис.

2. **Эффективность:** не нужно писать 4 отдельных SQL. Можно использовать один `SELECT COUNT(*) FROM ...` на таблицу, либо reuse существующие `list_*` если они уже делают `COUNT(*)` (но list-методы возвращают полные записи, что overkill для счётчика). Простые `COUNT(*)` — быстрее.

3. **Порядок действий:** сначала добавь `count()` в репозитории + покрой тестами, потом меняй dashboard handler + шаблон. Так сможешь проверить счётчики изолированно.

4. **Параллельность:** задача помечена `parallel-safe: true`, но она затрагивает слои репозиториев и admin-роут. Убедись, что никакая другая задача сейчас не трогает те же файлы.

5. **Пример существующего паттерна:** смотри `CategoryService` или `EventService` — как они вызывают репозитории. Сделай аналогично для `DashboardService.get_counters()`.
