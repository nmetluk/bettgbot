"""Модель `BackupRun` — журнал запусков бэкапов (для heartbeat-мониторинга TASK-099)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, String, Text, func, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BackupRun(Base):
    __tablename__ = "backup_run"
    __table_args__ = (Index("ix_backup_run_finished_at", text("finished_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # running | success | failed
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    replicated_at: Mapped[datetime | None] = mapped_column(
        postgresql.TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BackupRun id={self.id} status={self.status!r} started_at={self.started_at}>"
