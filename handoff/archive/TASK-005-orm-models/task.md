---
id: TASK-005
created: 2026-05-23
author: cowork-agent
parallel-safe: false
blockedBy: []
related:
  - docs/03-data-model.md
  - docs/08-conventions.md
  - state/GLOSSARY.md
priority: high
estimate: L
---

# TASK-005: ORM-модели всех сущностей

## Контекст

После TASK-004 у нас есть типизированный конфиг и логирование. Дальше — доменный слой. Эта задача создаёт **только декларацию моделей** (SQLAlchemy 2.0 `Mapped`/`mapped_column`); engine, sessionmaker и миграции — в TASK-006. Репозитории и сервисы — в TASK-007 и далее.

Источник истины по сущностям, полям, индексам и инвариантам — [docs/03-data-model.md](../../docs/03-data-model.md). Имена строго из [state/GLOSSARY.md](../../state/GLOSSARY.md). Стиль кода — [docs/08-conventions.md](../../docs/08-conventions.md): модели — только schema, никаких бизнес-методов; все timestamp'ы — `timestamptz`; ID — `BigInteger`.

## Перед стартом — pre-task cleanup PR

Перед основной работой проверь дерево и `origin/main` ([handoff/README.md#pre-task-cleanup-pr](../README.md#pre-task-cleanup-pr)). По состоянию на постановку правки cowork есть: обновлённые `state/PROJECT_STATUS.md` (закрытие TASK-004, новые следующие шаги) и `state/DECISIONS.md` (три новые записи по TASK-004), новая сессия `sessions/2026-05-23-03-task-004-review/`. Упакуй в `chore/post-TASK-004-cowork-cleanup`, открой PR, замерджи. После — ветка `feature/TASK-005-orm-models` от свежего `main`.

## Цель

В `src/shared/models/` лежат восемь моделей с правильно описанными типами, индексами, CHECK-ограничениями и relationships. `Base.metadata` отражает полную схему БД, описанную в [docs/03-data-model.md](../../docs/03-data-model.md). Unit-тесты на метаданные проверяют наличие всех таблиц, ключевых колонок, индексов и ограничений — без поднятия реальной БД.

## Definition of Done

### Файлы и структура

- [ ] `src/shared/models/base.py`:
  - `class Base(DeclarativeBase)` — корневой класс декларативного маппинга
  - common-аннотации через `type_annotation_map` (опционально): `datetime` → `TIMESTAMP(timezone=True)`, `dict[str, Any]` → `JSONB`
  - module docstring
- [ ] `src/shared/models/user.py` — `class User(Base)`
- [ ] `src/shared/models/category.py` — `class Category(Base)`
- [ ] `src/shared/models/event.py` — `class Event(Base)`
- [ ] `src/shared/models/outcome.py` — `class Outcome(Base)`
- [ ] `src/shared/models/prediction.py` — `class Prediction(Base)`
- [ ] `src/shared/models/reminder_setting.py` — `class ReminderSetting(Base)`
- [ ] `src/shared/models/admin_user.py` — `class AdminUser(Base)`
- [ ] `src/shared/models/audit_log.py` — `class AuditLog(Base)`
- [ ] `src/shared/models/__init__.py`:
  - re-export `Base`, всех моделей
  - `__all__` с полным списком
  - модуль-докстринг с одной фразой про назначение пакета
- [ ] `src/shared/__init__.py` обновлён: дополнительные re-exports из `models` **не нужны** (потребители импортируют как `from src.shared.models import User, Event, ...`), но проверь, что smoke-тест из TASK-002 не сломан.

### Поля и типы

Все поля — строго по таблицам в [docs/03-data-model.md](../../docs/03-data-model.md). Особое внимание:

- **ID** — `BigInteger` с `autoincrement=True`; первичный ключ через `mapped_column(primary_key=True)`.
- **Timestamp'ы** — `TIMESTAMP(timezone=True)`. `created_at`/`updated_at`/`archived_at`/`last_seen_at`/`last_login_at` — все с `tz`.
- **Серверные дефолты** — `created_at: Mapped[datetime] = mapped_column(server_default=func.now())`. Для `updated_at` — `server_default=func.now(), onupdate=func.now()`.
- **JSONB** — `from sqlalchemy.dialects.postgresql import JSONB`. Поля: `Event.metadata`, `AuditLog.payload`.

  ⚠️ Имя поля в `Event` — **не `metadata`**, потому что это зарезервированный атрибут `DeclarativeBase`. Используй имя колонки `metadata_` в Python и явный `name="metadata"` в `mapped_column`. Или — переименуй в `Event.extra` (Python) с `name="metadata"` (SQL). Выбери первый вариант (`metadata_`), он понятнее.

- **`int[]`** для `ReminderSetting.offsets_minutes` — `from sqlalchemy.dialects.postgresql import ARRAY`, тип `ARRAY(Integer)`. Default — пустой массив `server_default="{}"` или Python-default `default=list`.
- **`String(length)`** — длины задавай явно: phone — `String(20)` (E.164 не длиннее 16, запас), tg_username — `String(64)`, first_name/last_name — `String(64)`, Category.name — `String(64)`, Category.slug — `String(64)`, Event.title — `String(255)`, Outcome.label — `String(128)`, AdminUser.login — `String(64)`, AdminUser.password_hash — `String(128)`, AuditLog.action — `String(64)`. Описания (`description`, `full_name`) — `Text`, nullable.
- **Booleans** — `Boolean`, серверный дефолт `server_default=expression.false()`/`true()` из `sqlalchemy.sql.expression`.

### Внешние ключи и циклические зависимости

- **`Event.result_outcome_id` → `Outcome.id`** и **`Outcome.event_id` → `Event.id`** — циклическая зависимость. Стандартная техника:
  - На `Event.result_outcome_id` — `ForeignKey("outcome.id", use_alter=True, name="fk_event_result_outcome_id", ondelete="RESTRICT")`.
  - На `Outcome.event_id` — обычный `ForeignKey("event.id", ondelete="CASCADE")` (при удалении события стираются и его исходы; на практике события не удаляются — но Cascade корректно описывает теоретическую зависимость).
- **`Prediction.user_id` → `User.id`** — `ondelete="RESTRICT"` (пользователь не удаляется, только блокируется).
- **`Prediction.event_id` → `Event.id`** — `ondelete="RESTRICT"`.
- **`Prediction.outcome_id` → `Outcome.id`** — `ondelete="RESTRICT"` (Outcome нельзя удалить, если на него есть прогнозы).
- **`ReminderSetting.user_id`** — `primary_key=True`, `ForeignKey("user.id", ondelete="CASCADE")`.
- **`Event.created_by_admin_id` → `AdminUser.id`** — `ondelete="RESTRICT"`.
- **`AuditLog.admin_id` → `AdminUser.id`** — `ondelete="RESTRICT"`.
- **`Category.id` ← `Event.category_id`** — `ondelete="RESTRICT"` (категория не удалится, если в ней есть события; описано в [docs/03-data-model.md](../../docs/03-data-model.md)).

### Индексы

Все из секции «Индексы» в [docs/03-data-model.md](../../docs/03-data-model.md). Объявляй через `__table_args__ = (Index(...), UniqueConstraint(...), CheckConstraint(...))`. Имена индексов префиксом `ix_<table>_<cols>`; для partial — `ix_<table>_<cols>_partial`. Пример:

```python
__table_args__ = (
    Index("ix_event_published_archived_starts_at", "is_published", "is_archived", "starts_at"),
    Index("ix_event_category_starts_at", "category_id", "starts_at"),
    Index(
        "ix_event_predictions_close_at_active",
        "predictions_close_at",
        postgresql_where=text("NOT is_archived"),
    ),
    CheckConstraint("predictions_close_at <= starts_at", name="ck_event_close_before_start"),
    CheckConstraint(
        "(result_outcome_id IS NULL AND is_archived = false) OR "
        "(result_outcome_id IS NOT NULL AND is_archived = true AND archived_at IS NOT NULL)",
        name="ck_event_result_archive_consistency",
    ),
)
```

### CHECK-ограничения (DB-level инварианты)

Из [docs/03-data-model.md](../../docs/03-data-model.md):

- `Event`:
  - `ck_event_close_before_start`: `predictions_close_at <= starts_at`
  - `ck_event_result_archive_consistency`: см. выше (комбинирует два инварианта про result/archived)
- Остальные сущности — CHECK не требуют (инварианты енфорсятся на уровне сервиса).

⚠️ **Инвариант «нельзя опубликовать event с менее чем 2 outcomes»** — НЕ DB-level (его невозможно выразить разумно). Он живёт в сервисном слое (TASK-007 и далее). Здесь только комментарий в docstring `Event`, что это правило — на стороне `EventService`.

### Relationships

Через `relationship()` с `back_populates`. Без `lazy="joined"` (это AsyncIO — eager-loading через `selectinload`/`joinedload` решается на уровне query). Для Optional — `Optional[...] | None`.

- `User.predictions: Mapped[list[Prediction]]`
- `User.reminder_setting: Mapped[ReminderSetting | None]` (one-to-one, `uselist=False`)
- `Category.events: Mapped[list[Event]]`
- `Event.category: Mapped[Category]`
- `Event.outcomes: Mapped[list[Outcome]]` (back_populates="event", `foreign_keys=[Outcome.event_id]`)
- `Event.predictions: Mapped[list[Prediction]]`
- `Event.result_outcome: Mapped[Outcome | None]` (m2o, `foreign_keys=[Event.result_outcome_id]`)
- `Event.created_by_admin: Mapped[AdminUser]`
- `Outcome.event: Mapped[Event]` (back_populates="outcomes", `foreign_keys=[Outcome.event_id]`)
- `Outcome.predictions: Mapped[list[Prediction]]`
- `Prediction.user: Mapped[User]`
- `Prediction.event: Mapped[Event]`
- `Prediction.outcome: Mapped[Outcome]`
- `ReminderSetting.user: Mapped[User]`
- `AdminUser.events_created: Mapped[list[Event]]`
- `AdminUser.audit_logs: Mapped[list[AuditLog]]`
- `AuditLog.admin: Mapped[AdminUser]`

Для циклической `Event ↔ Outcome` — обязательно явные `foreign_keys=[...]` (SQLAlchemy сама не угадает, какой FK имеется в виду).

### Уникальные ограничения

- `User`: `UniqueConstraint("tg_user_id")`, `UniqueConstraint("phone")` — либо как `unique=True` на колонках напрямую (SQLAlchemy сгенерирует имя), либо явно в `__table_args__` с именами `uq_user_tg_user_id`, `uq_user_phone`. Используй явные имена — это упрощает миграции и дебаг.
- `Category`: `unique(name)`, `unique(slug)`.
- `AdminUser`: `unique(login)`.
- `Prediction`: `UniqueConstraint("user_id", "event_id", name="uq_prediction_user_event")` — один прогноз пользователя на событие.

### Тесты

`tests/unit/models/`:

- [ ] `tests/unit/models/__init__.py` (пустой)
- [ ] `tests/unit/models/test_metadata.py`:
  - `test_all_tables_registered` — все 8 таблиц зарегистрированы в `Base.metadata.tables`
  - `test_user_columns` — у `User` есть все ожидаемые колонки с правильными типами
  - `test_event_check_constraints` — у `event` таблицы есть `ck_event_close_before_start` и `ck_event_result_archive_consistency`
  - `test_prediction_unique_user_event` — `uq_prediction_user_event` объявлен
  - `test_indexes` — индексы из спеки присутствуют (минимум: `ix_event_published_archived_starts_at`, `ix_prediction_user_created_at`, `ix_audit_log_created_at`)
  - `test_event_metadata_jsonb_column` — колонка с SQL-именем `metadata` существует (Python-имя `metadata_`)
- [ ] `tests/unit/models/test_relationships.py`:
  - Для каждой связи проверить, что `relationship` объявлен и направление `back_populates` симметрично
  - Использовать `inspect(Model).relationships[name]` (SQLAlchemy inspect API), `.argument`, `.back_populates`
- [ ] Smoke-тест из TASK-002 продолжает проходить.

### Качество

- [ ] `uv run mypy src/shared` — зелёный (strict).
- [ ] `uv run ruff check src tests` — зелёный.
- [ ] `uv run ruff format --check src tests` — зелёный.
- [ ] `uv run pytest` — все тесты зелёные.
- [ ] CI на PR — зелёный.

### Workflow

- [ ] Ветка `feature/TASK-005-orm-models`, Conventional Commits, PR.
- [ ] Отчёт `handoff/outbox/TASK-005-report.md`.
- [ ] Задача → `handoff/archive/TASK-005-orm-models/task.md`.

## Артефакты

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
- src/shared/.gitkeep (был удалён ещё в TASK-002 — проверь, что папка models не плодит .gitkeep)
```

## Ссылки

- [docs/03-data-model.md](../../docs/03-data-model.md) — ERD, поля, индексы, инварианты (главный источник истины)
- [docs/08-conventions.md](../../docs/08-conventions.md) — naming, типизация, «модели — только schema»
- [state/GLOSSARY.md](../../state/GLOSSARY.md) — имена классов и атрибутов

## Подсказки исполнителю

- **`type_annotation_map` в Base** — удобный способ один раз сказать SQLAlchemy 2.0, что `datetime` это `TIMESTAMP(timezone=True)`, а `dict[str, Any]` — `JSONB`. Тогда в моделях можно писать `created_at: Mapped[datetime]` без `mapped_column(TIMESTAMP(...))`. Это сокращает шум.
- **`Event.metadata_` (Python) → колонка `metadata` (SQL).** Префикс/суффикс `_` стандартное соглашение pep8 для конфликта с keyword/reserved. Маппится через `mapped_column("metadata", JSONB, ...)`.
- **PostgreSQL-specific типы** — импортируй из `sqlalchemy.dialects.postgresql` (`JSONB`, `ARRAY`). Не из `sqlalchemy` (там JSON — generic, нам не подходит).
- **Partial index** через `Index(..., postgresql_where=text("..."))`. Нужен `text` из `sqlalchemy`.
- **CHECK-выражения** — текст SQL внутри `CheckConstraint("...")`. Двойные скобки, чтобы Python не запутался с f-string.
- **Имена FK/индексов/CHECK** — не полагайся на автогенерируемые SQLAlchemy. Это поможет в TASK-006 (читаемые миграции) и при дебаге в проде. Соглашение:
  - PK: `pk_<table>`
  - FK: `fk_<table>_<col>`
  - Unique: `uq_<table>_<col(s)>`
  - Index: `ix_<table>_<col(s)>`
  - Check: `ck_<table>_<rule>`
- **Naming convention для SQLAlchemy глобально** — задаётся через `MetaData(naming_convention={...})`, передаётся в `DeclarativeBase`'у. Это автоматически даст осмысленные имена для безымянных ограничений. Стандартный snippet:

  ```python
  from sqlalchemy import MetaData
  NAMING_CONVENTION = {
      "ix": "ix_%(table_name)s_%(column_0_N_name)s",
      "uq": "uq_%(table_name)s_%(column_0_N_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  metadata_obj = MetaData(naming_convention=NAMING_CONVENTION)

  class Base(DeclarativeBase):
      metadata = metadata_obj
  ```

  Используй этот стиль. Тогда можно не задавать имена явно у каждой колонки/индекса — SQLAlchemy сгенерирует читаемые по шаблону. Явно — только для CHECK (там нет `column_0_name`, нужен ручной `name=`).
- **Inspect API в тестах** — `from sqlalchemy import inspect; inspect(User).columns["phone"].type.length` и т.п. Для constraints — итерируй `Base.metadata.tables["event"].constraints`.
- **mypy strict + SQLAlchemy 2.0** — типы `Mapped[...]` корректно понимаются с актуальным `sqlalchemy[mypy]` extra. Если будут жалобы — это проявится сразу; почини точечно, без отключения strict.
- **Без бизнес-методов** ([docs/08-conventions.md](../../docs/08-conventions.md)). `__repr__` для удобства логов — допустимо (короткий, без рекурсии в relationships).

## Что НЕ делать

- Не подключать Alembic, не писать миграций. Это TASK-006.
- Не создавать `src/shared/db.py` с engine/sessionmaker. Тоже TASK-006.
- Не писать репозитории, сервисы, фабрики. Это TASK-007/008.
- Не добавлять в `Event` сервисное правило «нельзя опубликовать без 2+ outcomes» как DB-constraint — оно сервисное (только комментарий в docstring).
- Не лезть в `docs/`, `state/`, `sessions/`, `README.md`, `CLAUDE.md` (кроме исправлений собственного docstring, если найдёшь несоответствие — спрашивай через `outbox/TASK-005-question.md`).
- Не добавлять зависимости. `sqlalchemy[asyncio]` уже в `pyproject.toml`.
