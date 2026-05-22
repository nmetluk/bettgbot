"""Тесты relationships между ORM-моделями."""

from __future__ import annotations

from sqlalchemy import inspect
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

# (Owner, attr, Target, back_populates) — пары и направление обратной связи.
RELATIONSHIPS: list[tuple[type[Base], str, type[Base], str | None]] = [
    (User, "predictions", Prediction, "user"),
    (User, "reminder_setting", ReminderSetting, "user"),
    (Category, "events", Event, "category"),
    (Event, "category", Category, "events"),
    (Event, "outcomes", Outcome, "event"),
    (Event, "predictions", Prediction, "event"),
    (Event, "result_outcome", Outcome, None),  # без back_populates (m2o без обратной коллекции)
    (Event, "created_by_admin", AdminUser, "events_created"),
    (Outcome, "event", Event, "outcomes"),
    (Outcome, "predictions", Prediction, "outcome"),
    (Prediction, "user", User, "predictions"),
    (Prediction, "event", Event, "predictions"),
    (Prediction, "outcome", Outcome, "predictions"),
    (ReminderSetting, "user", User, "reminder_setting"),
    (AdminUser, "events_created", Event, "created_by_admin"),
    (AdminUser, "audit_logs", AuditLog, "admin"),
    (AuditLog, "admin", AdminUser, "audit_logs"),
]


def test_relationships_present_and_symmetric() -> None:
    for owner, attr, target, back in RELATIONSHIPS:
        rels = inspect(owner).relationships
        assert attr in rels, f"{owner.__name__}.{attr} missing"
        rel = rels[attr]
        assert rel.mapper.class_ is target, (
            f"{owner.__name__}.{attr} → expected {target.__name__}, "
            f"got {rel.mapper.class_.__name__}"
        )
        if back is None:
            assert rel.back_populates is None, (
                f"{owner.__name__}.{attr} expected no back_populates, got {rel.back_populates!r}"
            )
        else:
            assert rel.back_populates == back, (
                f"{owner.__name__}.{attr}.back_populates = {rel.back_populates!r}, "
                f"expected {back!r}"
            )


def test_event_outcome_cyclic_relationships_use_explicit_foreign_keys() -> None:
    outcomes_rel = inspect(Event).relationships["outcomes"]
    result_rel = inspect(Event).relationships["result_outcome"]
    # Если FK неявные, два relationships между теми же таблицами не разрешились бы.
    assert outcomes_rel.local_columns != result_rel.local_columns
    # У result_outcome локальная колонка — result_outcome_id.
    result_local = {c.name for c in result_rel.local_columns}
    assert result_local == {"result_outcome_id"}


def test_reminder_setting_is_one_to_one() -> None:
    rs_rel = inspect(User).relationships["reminder_setting"]
    assert rs_rel.uselist is False
