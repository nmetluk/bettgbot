"""Модель `User` — Telegram-пользователь, прошедший проверку по номеру."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import false

from .base import Base

if TYPE_CHECKING:
    from .prediction import Prediction
    from .reminder_setting import ReminderSetting


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("tg_user_id", name="uq_user_tg_user_id"),
        UniqueConstraint("phone", name="uq_user_phone"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="user")
    reminder_setting: Mapped[ReminderSetting | None] = relationship(
        back_populates="user", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_user_id={self.tg_user_id}>"
