"""Модель `ReminderSetting` — per-user настройки напоминаний."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import true

from .base import Base

if TYPE_CHECKING:
    from .user import User


class ReminderSetting(Base):
    __tablename__ = "reminder_setting"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE", name="fk_reminder_setting_user_id_user"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)
    offsets_minutes: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), server_default="{}", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="reminder_setting")

    def __repr__(self) -> str:
        return f"<ReminderSetting user_id={self.user_id} enabled={self.enabled}>"
