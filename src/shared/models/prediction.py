"""Модель `Prediction` — связка «пользователь × событие × выбранный исход»."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .event import Event
    from .outcome import Outcome
    from .user import User


class Prediction(Base):
    __tablename__ = "prediction"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_prediction_user_event"),
        Index(
            "ix_prediction_user_id_created_at",
            "user_id",
            text("created_at DESC"),
        ),
        Index("ix_prediction_event_id", "event_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="RESTRICT", name="fk_prediction_user_id_user"),
        nullable=False,
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event.id", ondelete="RESTRICT", name="fk_prediction_event_id_event"),
        nullable=False,
    )
    outcome_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outcome.id", ondelete="RESTRICT", name="fk_prediction_outcome_id_outcome"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    user: Mapped[User] = relationship(back_populates="predictions")
    event: Mapped[Event] = relationship(back_populates="predictions")
    outcome: Mapped[Outcome] = relationship(back_populates="predictions")

    def __repr__(self) -> str:
        return (
            f"<Prediction id={self.id} user_id={self.user_id} "
            f"event_id={self.event_id} outcome_id={self.outcome_id}>"
        )
