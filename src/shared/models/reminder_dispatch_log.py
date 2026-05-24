"""Модель `ReminderDispatchLog` — дедупликация отправленных напоминаний (TASK-017)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .event import Event
    from .user import User


class ReminderDispatchLog(Base):
    __tablename__ = "reminder_dispatch_log"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "event_id",
            "offset_minutes",
            name="uq_reminder_dispatch_log_user_event_offset",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "user.id",
            ondelete="CASCADE",
            name="fk_reminder_dispatch_log_user_id_user",
        ),
        nullable=False,
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "event.id",
            ondelete="CASCADE",
            name="fk_reminder_dispatch_log_event_id_event",
        ),
        nullable=False,
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    dispatched_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship()
    event: Mapped[Event] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ReminderDispatchLog user_id={self.user_id} event_id={self.event_id} "
            f"offset={self.offset_minutes}>"
        )
