"""Модель `BroadcastDelivery` — лог доставки broadcast-сообщения (идемпотентность)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BroadcastDelivery(Base):
    """Лог доставки broadcast-сообщения конкретному пользователю.

    Идемпотентность: UNIQUE на (broadcast_id, user_id) гарантирует,
    что при рестарте job'а сообщение не будет отправлено дважды.

    Паттерн зеркалирует `ReminderDispatchLog` (TASK-017).
    """

    __tablename__ = "broadcast_delivery"

    broadcast_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )
    delivered_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    # Инварианты
    __table_args__ = (UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_delivery"),)

    def __repr__(self) -> str:
        return f"<BroadcastDelivery broadcast_id={self.broadcast_id} user_id={self.user_id}>"
