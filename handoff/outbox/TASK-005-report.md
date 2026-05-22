---
task: TASK-005
completed: 2026-05-23
agent: claude-code-local
status: done
pr: https://github.com/nmetluk/bettgbot/pull/11
branch: feature/TASK-005-orm-models
commits:
  - b21a8b5 feat(models): base + 8 ORM models per docs/03-data-model.md
  - 40389b4 test(models): 22 metadata + relationship assertions
---

# Отчёт по TASK-005: ORM-модели всех сущностей

## Сводка

Доменный слой описан декларациями SQLAlchemy 2.0 (`Mapped` / `mapped_column`). Восемь моделей в `src/shared/models/`: `User`, `Category`, `Event`, `Outcome`, `Prediction`, `ReminderSetting`, `AdminUser`, `AuditLog`. Корневой `Base` фиксирует naming convention (`pk_<table>`, `fk_<table>_<col>_<ref>`, `uq_<table>_<cols>`, `ix_<table>_<cols>`, `ck_<table>_<rule>`) и `type_annotation_map`, по которому `datetime` автоматически становится `TIMESTAMP(timezone=True)`, а `dict[str, Any]` — `JSONB`. Engine, sessionmaker и миграции — отдельная задача (TASK-006).

Сложные места: циклическая зависимость `Event ↔ Outcome` разрешена через `use_alter=True` на `Event.result_outcome_id` плюс явные `foreign_keys=[...]` в двух relationships Event → Outcome. Поле JSONB-метаданных в `Event` зовётся `metadata_` в Python (потому что `metadata` зарезервировано на `DeclarativeBase`), но колонка в SQL — `metadata` через `mapped_column("metadata", ...)`.

Особенность naming convention: для `ck_` правила SQLAlchemy достраивает префикс к переданному `name=`, поэтому в `CheckConstraint(name=...)` передаётся только суффикс (`close_before_start`, `result_archive_consistency`) — финальное имя получается как `ck_event_<суффикс>`. Для `uq`/`fk`/`ix` явное `name=` подавляет convention, и приходится писать полное имя — это попало в отчёт как открытый вопрос для согласования.

Перед основной работой сделан pre-task cleanup PR [#10](https://github.com/nmetluk/bettgbot/pull/10) (post-TASK-004 правки cowork: state-файлы и сессия приёмки).

## Изменённые файлы

```
+ src/shared/models/__init__.py
+ src/shared/models/base.py
+ src/shared/models/user.py
+ src/shared/models/category.py
+ src/shared/models/event.py
+ src/shared/models/outcome.py
+ src/shared/models/prediction.py
+ src/shared/models/reminder_setting.py
+ src/shared/models/admin_user.py
+ src/shared/models/audit_log.py
+ tests/unit/models/__init__.py
+ tests/unit/models/test_metadata.py
+ tests/unit/models/test_relationships.py
* handoff/inbox/TASK-005-orm-models.md → in-progress → archive (этот PR)
+ handoff/archive/TASK-005-orm-models/task.md
+ handoff/outbox/TASK-005-report.md
```

## Тесты

```
22 passed in 0.26s

tests/unit/test_smoke.py                  ✓
tests/unit/test_config.py                 ✓ 5
tests/unit/test_logging.py                ✓ 3
tests/unit/models/test_metadata.py        ✓ 10
tests/unit/models/test_relationships.py   ✓ 3
```

`mypy src/shared` strict — `Success: no issues found in 13 source files`. `ruff check`, `ruff format --check` — зелёные. CI на PR [#11](https://github.com/nmetluk/bettgbot/pull/11) — все три job'а зелёные.

## Архитектурные детали (для TASK-006+)

- **Naming convention** задана глобально в `Base.metadata`. Alembic в TASK-006 должен передать `target_metadata = Base.metadata` — тогда autogenerate будет генерировать миграции с этими же именами.
- **`use_alter=True`** на `Event.result_outcome_id` означает, что при создании схемы SQLAlchemy `CREATE TABLE event` без этого FK, а потом `ALTER TABLE event ADD CONSTRAINT fk_event_result_outcome_id`. Alembic это поддерживает, но autogenerate может потребовать ручной правки порядка операций.
- **`ondelete`**: `RESTRICT` почти везде (User не удаляется — блокируется; Prediction не удаляется), `CASCADE` для `Outcome.event_id` и `ReminderSetting.user_id` (теоретические зависимости).
- **Server defaults** через `func.now()` (timestamp) и `expression.true()/false()` (bool). `Prediction.updated_at` имеет `onupdate=func.now()`.
- **`ARRAY(Integer)` из `sqlalchemy.dialects.postgresql`** для `ReminderSetting.offsets_minutes`. Server default `'{}'`; бизнес-дефолт `[1440, 60]` ставит сервис.
- **`Event.metadata_` nullable** — оставлено опциональным; если хочется NOT NULL DEFAULT `{}`, см. открытый вопрос #1 ниже.

## Как воспроизвести / запустить

```bash
git checkout main
uv sync --frozen
uv run pytest tests/unit/models -v
uv run mypy src/shared
```

## Что не сделано / вынесено

1. **Engine, sessionmaker, `get_session()`** — TASK-006 (`src/shared/db.py`).
2. **Alembic init + первая миграция `0001_init.py`** — TASK-006.
3. **Репозитории, сервисы, фабрики, factories для тестов** — TASK-007 и далее.
4. **Сервисный инвариант** «нельзя опубликовать Event с < 2 Outcomes» — только комментарий в docstring `Event`. Реализация в `EventService` (TASK-007+).
5. **Round-trip-тесты** с реальным postgres — будут в TASK-006 после поднятия sessionmaker.

## Открытые вопросы для проектировщика

1. **`Event.metadata_`: nullable vs NOT NULL DEFAULT `{}`.** Сейчас nullable. Альтернатива — `server_default="{}"`, `nullable=False` — тогда код не должен проверять на None. Какой UX?
2. **`AdminUser.full_name` тип.** DoD просил `Text`, спецификация (`docs/03-data-model.md`) говорит `string`. Поставил `Text` (nullable). Заменить на `String(128)` (или другой лимит)?
3. **Имена в Constraint vs naming convention.** Для `uq`/`fk`/`ix` явное `name=` подавляет convention — я передаю полные имена. Для `ck` convention достраивает префикс — я передаю только суффикс. Это работает, но не единообразно. Альтернатива — изменить convention `ck` на `%(constraint_name)s` (без префикса), и тогда везде передавать полное имя. Согласуем?
4. **`Prediction.is_correct` server_default.** Сейчас просто nullable, без `server_default=null()`. Это пробег по умолчанию для SQL, но если хочется явности — могу добавить.
5. **`ondelete="CASCADE"` для `Outcome.event_id`.** В DoD: «при удалении события стираются и его исходы; на практике события не удаляются — но Cascade корректно описывает теоретическую зависимость». ОК. Но это означает, что если в будущем появится ситуация хард-delete события (например, отмена через админку), исходы исчезнут — а с ними может что-то сломаться в логике (Prediction.outcome_id с RESTRICT станет недостижим). Возможно стоит RESTRICT и здесь? Решение остаётся на стороне сервиса.

## Предложение для PROJECT_STATUS.md

```markdown
- 2026-05-23 — TASK-005: 8 ORM-моделей в `src/shared/models/` по `docs/03-data-model.md` — `User`, `Category`, `Event`, `Outcome`, `Prediction`, `ReminderSetting`, `AdminUser`, `AuditLog`. Naming convention, type_annotation_map, циклика Event↔Outcome через `use_alter`, partial-index, CHECK на Event. 13 unit-тестов на метаданные/relationships. PR [#11](https://github.com/nmetluk/bettgbot/pull/11) → squash `0984fbb`. Pre-task cleanup [#10](https://github.com/nmetluk/bettgbot/pull/10).
```

## Метрики

- Файлов добавлено: 13 (10 модели, 3 тесты)
- Строк кода: ~470 (models) + ~210 (tests)
- Тестов: 13 новых (22 всего)
- Время на выполнение: ~45 мин (включая cleanup PR)
