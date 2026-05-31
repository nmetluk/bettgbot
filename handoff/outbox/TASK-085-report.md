---
task: TASK-085
completed: 2026-05-31
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/160
branch: feature/TASK-085-broadcast-category-fk-vs-check
commits:
  - fb5ee9c feat(shared,admin): TASK-085 broadcast.category_id FK RESTRICT + CategoryHasBroadcastsError (M1 from audit)
---

# Отчёт по TASK-085: Согласовать broadcast.category_id FK и CHECK (целостность при удалении категории)

## Сводка

Выбран **Вариант A (RESTRICT)** — рекомендуемый по умолчанию.

Реализовано:
- FK `fk_broadcast_category_id` изменён с `ondelete="SET NULL"` на `"RESTRICT"` (модель + миграция `0006_broadcast_category_restrict`).
- `CategoryRepository` получил явные `has_events()` / `has_broadcasts()` (лёгкие COUNT).
- `CategoryService.delete_category` теперь делает pre-check'и **до** DELETE — убрана хрупкая catch-all `IntegrityError → HasEventsError` (улучшение заодно с задачей).
- Новая доменная ошибка `CategoryHasBroadcastsError` (по образцу HasEventsError).
- Admin handler возвращает 302 с `?error=has_broadcasts`, шаблон показывает золотой warning-alert.
- `docs/03-data-model.md` обновлён (семантика удаления Category + Broadcast).
- 2 новых теста (integration на реальном PG + unit handler) — воспроизводят точный сценарий "рассылка segment=category → блокировка удаления".

Все тесты, линт, mypy зелёные. Миграция 0006 проходит upgrade/downgrade в рамках существующих integration-тестов миграций.

## Коммиты и PR
- PR #160 (squash-merge ожидается автоматически после зелёного CI)
- Коммит: fb5ee9c (на ветке feature/TASK-085-...)

## Изменённые файлы
```
+ src/migrations/versions/0006_broadcast_category_restrict.py
* src/shared/models/broadcast.py          # ondelete RESTRICT
* src/shared/repositories/category.py     # + has_events, has_broadcasts
* src/shared/services/category.py         # pre-check + CategoryHasBroadcastsError
* src/shared/exceptions.py                # новый CategoryHasBroadcastsError + __all__
* src/admin/routes/categories.py          # catch + redirect has_broadcasts
* src/admin/templates/categories/list.html # alert для has_broadcasts
* tests/integration/services/test_category_service_crud.py
* tests/unit/admin/test_categories_handler.py
* docs/03-data-model.md
```

## Как воспроизвести / запустить
```bash
# локально (dev)
make up
uv run pytest tests/integration/services/test_category_service_crud.py -q -k "broadcasts or has_events"
uv run pytest tests/unit/admin/test_categories_handler.py -q

# проверить миграцию
uv run alembic current
# (в тестах fresh_db делает downgrade base + upgrade head — 0006 применяется)

# в админке (после логина): создать категорию → создать рассылку segment=category на неё → попытка удалить → alert "есть рассылки"
```

## Что не сделано (если применимо)
- Ничего. Полностью закрыт скоуп задачи (Variant A).
- Не стал делать Variant B (snapshot + relax CHECK) — нет требования удалять категории с историческими рассылками; RESTRICT проще, консистентнее, сохраняет смысл данных.

## Открытые вопросы для проектировщика
Нет.

## Предложение для PROJECT_STATUS.md
```markdown
- 2026-05-31 — **TASK-085 закрыт:** broadcast.category_id FK → RESTRICT (M1 аудита 2026-05-31/30). CategoryHasBroadcastsError + pre-check'и в CategoryService, миграция 0006, UI-alert в /categories. PR #160.
```

## Метрики (опционально)
- Тестов добавлено: 2 (1 integration, 1 unit)
- Время на выполнение: ~45 мин (включая анализ аудита, выбор варианта, рефакторинг catch-all, проверку миграций)
