"""Модель `Broadcast` — рассылка сообщения по сегменту пользователей."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .admin_user import AdminUser
    from .category import Category


class Broadcast(Base):
    """Рассылка сообщения выбранному сегменту пользователей.

    Статусы:
    - `draft`: черновик (создан, ещё не поставлен в очередь)
    - `queued`: в очереди на отправку (job заберёт в следующий тик)
    - `sending`: идёт отправка (job забрал, работает)
    - `done`: отправка завершена (успешно или частично)
    - `failed`: критический сбой (например, нет получателей)

    Сегменты:
    - `all`: все неблокированные пользователи
    - `active`: активные за последние 30 дней (last_seen_at >= now - 30d)
    - `category`: пользователи, делавшие прогнозы в событиях данной категории
    """

    __tablename__ = "broadcast"

    # Поля
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    segment: Mapped[Literal["all", "active", "category"]] = mapped_column(
        String(10), nullable=False
    )
    category_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("category.id", ondelete="SET NULL", name="fk_broadcast_category_id"),
        nullable=True,
    )

    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[Literal["draft", "queued", "sending", "done", "failed"]] = mapped_column(
        String(10), nullable=False, server_default="draft"
    )

    created_by_admin_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("admin_user.id", ondelete="RESTRICT", name="fk_broadcast_created_by"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Счётчики
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Отношения
    created_by: Mapped[AdminUser] = relationship(backref="broadcasts")
    category: Mapped[Category | None] = relationship(backref="broadcasts")

    # Инварианты
    __table_args__ = (
        CheckConstraint(
            "(segment = 'category' AND category_id IS NOT NULL) OR (segment != 'category')",
            name="ck_broadcast_category_required",
        ),
    )

    def __repr__(self) -> str:
        return f"<Broadcast id={self.id} segment={self.segment} status={self.status}>"
