"""Модель `AdminUser` — учётка администратора веб-админки."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import true

from .base import Base

if TYPE_CHECKING:
    from .audit_log import AuditLog
    from .event import Event


class AdminUser(Base):
    __tablename__ = "admin_user"
    __table_args__ = (UniqueConstraint("login", name="uq_admin_user_login"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    events_created: Mapped[list[Event]] = relationship(back_populates="created_by_admin")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="admin")

    def __repr__(self) -> str:
        return f"<AdminUser id={self.id} login={self.login!r}>"
