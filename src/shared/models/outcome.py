"""Модель `Outcome` — возможный вариант исхода события."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .event import Event
    from .prediction import Prediction


class Outcome(Base):
    __tablename__ = "outcome"
    __table_args__ = (Index("ix_outcome_event_id_sort_order", "event_id", "sort_order"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("event.id", ondelete="CASCADE", name="fk_outcome_event_id_event"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    event: Mapped[Event] = relationship(back_populates="outcomes", foreign_keys=[event_id])
    predictions: Mapped[list[Prediction]] = relationship(back_populates="outcome")

    def __repr__(self) -> str:
        return f"<Outcome id={self.id} event_id={self.event_id} label={self.label!r}>"
