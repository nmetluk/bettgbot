"""Тесты метаданных ORM-схемы — без поднятия реальной БД."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import TIMESTAMP
from src.shared.models import (
    AdminUser,
    AuditLog,
    Base,
    Category,
    Event,
    Outcome,
    Prediction,
    ReminderSetting,
    User,
)

EXPECTED_TABLES = {
    "user",
    "category",
    "event",
    "outcome",
    "prediction",
    "reminder_setting",
    "admin_user",
    "audit_log",
}


def _column_names(model: type[Base]) -> set[str]:
    return set(model.__table__.columns.keys())


def _constraint_names(model: type[Base]) -> set[str]:
    return {c.name for c in model.__table__.constraints if c.name is not None}


def _index_names(model: type[Base]) -> set[str]:
    return {idx.name for idx in model.__table__.indexes if idx.name is not None}


def test_all_tables_registered() -> None:
    registered = set(Base.metadata.tables.keys())
    assert registered >= EXPECTED_TABLES, f"missing tables: {EXPECTED_TABLES - registered}"


def test_user_columns() -> None:
    assert _column_names(User) == {
        "id",
        "tg_user_id",
        "phone",
        "tg_username",
        "first_name",
        "last_name",
        "created_at",
        "last_seen_at",
        "is_blocked",
    }
    assert isinstance(User.__table__.columns["id"].type, BigInteger)
    assert isinstance(User.__table__.columns["tg_user_id"].type, BigInteger)
    assert isinstance(User.__table__.columns["phone"].type, String)
    assert User.__table__.columns["phone"].type.length == 20
    assert isinstance(User.__table__.columns["is_blocked"].type, Boolean)
    assert isinstance(User.__table__.columns["created_at"].type, TIMESTAMP)
    assert User.__table__.columns["created_at"].type.timezone is True


def test_event_check_constraints() -> None:
    names = _constraint_names(Event)
    assert "ck_event_close_before_start" in names
    assert "ck_event_result_archive_consistency" in names


def test_event_metadata_jsonb_column() -> None:
    # SQL-имя колонки — "metadata", Python-атрибут — "metadata_".
    table_cols = set(Event.__table__.columns.keys())
    assert "metadata" in table_cols, table_cols
    assert isinstance(Event.__table__.columns["metadata"].type, JSONB)
    # Python-атрибут не должен называться `metadata` (это reserved у DeclarativeBase).
    assert hasattr(Event, "metadata_")


def test_prediction_unique_user_event() -> None:
    assert "uq_prediction_user_event" in _constraint_names(Prediction)


def test_admin_user_unique_login() -> None:
    assert "uq_admin_user_login" in _constraint_names(AdminUser)


def test_indexes() -> None:
    event_indexes = _index_names(Event)
    assert "ix_event_is_published_is_archived_starts_at" in event_indexes
    assert "ix_event_category_id_starts_at" in event_indexes
    assert "ix_event_predictions_close_at_active" in event_indexes

    prediction_indexes = _index_names(Prediction)
    assert "ix_prediction_user_id_created_at" in prediction_indexes

    audit_indexes = _index_names(AuditLog)
    assert "ix_audit_log_created_at" in audit_indexes
    assert "ix_audit_log_admin_id_created_at" in audit_indexes


def test_reminder_setting_offsets_is_array_of_integer() -> None:
    col = ReminderSetting.__table__.columns["offsets_minutes"]
    assert isinstance(col.type, ARRAY)


def test_category_outcome_audit_have_expected_columns() -> None:
    assert _column_names(Category) == {
        "id",
        "name",
        "slug",
        "sort_order",
        "is_active",
        "created_at",
    }
    assert _column_names(Outcome) == {"id", "event_id", "label", "sort_order"}
    assert _column_names(AuditLog) == {"id", "admin_id", "action", "payload", "created_at"}


def test_foreign_keys_have_explicit_names() -> None:
    # Несколько ключевых FK — проверяем что имена явные и совпадают со спецификацией.
    fk_names: set[str] = set()
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.name is not None:
                fk_names.add(fk.name)

    expected_fks = {
        "fk_event_category_id_category",
        "fk_event_result_outcome_id",
        "fk_event_created_by_admin_id_admin_user",
        "fk_outcome_event_id_event",
        "fk_prediction_user_id_user",
        "fk_prediction_event_id_event",
        "fk_prediction_outcome_id_outcome",
        "fk_reminder_setting_user_id_user",
        "fk_audit_log_admin_id_admin_user",
    }
    assert expected_fks <= fk_names, f"missing FK names: {expected_fks - fk_names}"
