---
task: TASK-043
completed: 2026-05-26
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/85
branch: feature/TASK-043-dashboard-counters
commits:
  - 9634736 feat(admin): implement dashboard counters
  - 6c182a5 fix(admin): remove asyncio.gather from DashboardService
  - 8c05dce style: run ruff format on test file
---

# Отчёт по TASK-043: Реализовать счётчики на дашборде админки

## Сводка

Реализованы реальные счётчики на главной странице админки вместо заглушек с нулями. Проблема была обнаружена после выкладки MVP на прод — дашборд показывал пустую статистику, что создавало плохое впечатление.

**Принятое решение:** использование последовательных вызовов вместо `asyncio.gather` — SQLAlchemy не поддерживает конкурентные операции на одной сессии. Для простых COUNT(*) запросов накладные расходы минимальны.

**Изменения:**
- Добавлены методы `count()` в `CategoryRepository` и `PredictionRepository`
- Создан `DashboardService` с методом `get_counters()`
- Handler `dashboard.py` теперь вызывает сервис вместо хардкода
- Шаблон очищен от warning-текста

## Изменённые файлы

```
* src/shared/repositories/category.py           # +count() метод
* src/shared/repositories/prediction.py         # +count() метод
* src/shared/services/__init__.py               # +DashboardService экспорт
+ src/shared/services/dashboard.py              # новый сервис
* src/admin/routes/dashboard.py                 # использует сервис
* src/admin/templates/dashboard.html            # убран warning
+ tests/unit/admin/test_dashboard_handler.py    # 2 unit-теста
* tests/integration/repositories/test_category_repository.py       # +2 теста count()
* tests/integration/repositories/test_prediction_repository.py     # +1 тест count()
```

## Как воспроизвести / запустить

```bash
# локально (требуется запущенная БД)
uv run pytest tests/unit/admin/test_dashboard_handler.py -v

# на прод VPS после merge
ssh -i ~/.ssh/bettgbot_deploy root@5.188.88.78
cd /opt/bettgbot/bettgbot
git pull && docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml build web
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.prod-no-domain.yml up -d web
```

После обновления дашборд по адресу `http://5.188.88.78:8888/admin` будет показывать реальные счётчики.

## Что не сделано

Ничего — все пункты DoD выполнены.

## Открытые вопросы для проектировщика

Нет.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-26 — **TASK-043 закрыт:** счётчики на дашборде админки — `DashboardService` с `get_counters()`, методы `count()` в Category/Prediction репозиториях, 2 unit + 3 integration теста. PR [#85](https://github.com/nmetluk/bettgbot/pull/85) → squash `9634736`. Исправлен hotfix: `asyncio.gather` заменён на последовательные вызовы (SQLAlchemy limitation).
```

## Метрики

- Тестов добавлено: 5 (2 unit + 3 integration)
- Время на выполнение: ~1.5 часа
