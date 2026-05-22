"""Модель `Event` — центральная сущность: событие, на исход которого делают прогноз.

Инварианты, не выраженные на уровне БД:
- Невозможно опубликовать событие (`is_published = true`), у которого менее
  двух связанных `Outcome`. Этот инвариант — на стороне `EventService`
  (см. TASK-007+), не CHECK-constraint.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false

from .base import Base

if TYPE_CHECKING:
    from .admin_user import AdminUser
    from .category import Category
    from .outcome import Outcome
    from .prediction import Prediction


class Event(Base):
    __tablename__ = "event"
    __table_args__ = (
        Index(
            "ix_event_is_published_is_archived_starts_at",
            "is_published",
            "is_archived",
            "starts_at",
        ),
        Index("ix_event_category_id_starts_at", "category_id", "starts_at"),
        Index(
            "ix_event_predictions_close_at_active",
            "predictions_close_at",
            postgresql_where=text("NOT is_archived"),
        ),
        # Naming convention `ck` достраивает префикс `ck_<table>_`, поэтому здесь
        # передаём только суффикс — финальное имя соберётся как `ck_event_<suffix>`.
        CheckConstraint(
            "predictions_close_at <= starts_at",
            name="close_before_start",
        ),
        CheckConstraint(
            "(result_outcome_id IS NULL AND is_archived = false) OR "
            "(result_outcome_id IS NOT NULL AND is_archived = true "
            "AND archived_at IS NOT NULL)",
            name="result_archive_consistency",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("category.id", ondelete="RESTRICT", name="fk_event_category_id_category"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SQL-имя — "metadata"; Python-имя — "metadata_", потому что `metadata`
    # зарезервировано в `DeclarativeBase` (это MetaData).
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", nullable=True)
    starts_at: Mapped[datetime] = mapped_column(nullable=False)
    predictions_close_at: Mapped[datetime] = mapped_column(nullable=False)
    result_outcome_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "outcome.id",
            use_alter=True,
            name="fk_event_result_outcome_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    created_by_admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "admin_user.id",
            ondelete="RESTRICT",
            name="fk_event_created_by_admin_id_admin_user",
        ),
        nullable=False,
    )

    category: Mapped[Category] = relationship(back_populates="events")
    outcomes: Mapped[list[Outcome]] = relationship(
        back_populates="event",
        foreign_keys="Outcome.event_id",
    )
    predictions: Mapped[list[Prediction]] = relationship(back_populates="event")
    result_outcome: Mapped[Outcome | None] = relationship(
        foreign_keys=[result_outcome_id],
    )
    created_by_admin: Mapped[AdminUser] = relationship(back_populates="events_created")

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"
