"""Модель `Category` — папка событий."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.expression import true

from .base import Base

if TYPE_CHECKING:
    from .event import Event


class Category(Base):
    __tablename__ = "category"
    __table_args__ = (
        UniqueConstraint("name", name="uq_category_name"),
        UniqueConstraint("slug", name="uq_category_slug"),
        Index("ix_category_is_active_sort_order", "is_active", "sort_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    events: Mapped[list[Event]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} slug={self.slug!r}>"
