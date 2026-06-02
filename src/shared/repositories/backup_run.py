"""`BackupRunRepository` — запросы к таблице `backup_run` (для heartbeat TASK-099 + replication TASK-100).

Запись в таблицу делает скрипт контейнера db-backup через psql (не Python).
Репо предоставляет read-хелперы (get_latest, get_last_success, get_last_unreplicated_success) и mark_replicated.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BackupRun

__all__ = ["BackupRunRepository"]


class BackupRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest(self) -> BackupRun | None:
        """Последняя запись о бэкапе (любого статуса)."""
        stmt = (
            select(BackupRun)
            .order_by(BackupRun.finished_at.desc().nulls_last(), BackupRun.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_last_success(self) -> BackupRun | None:
        """Последняя успешная запись о бэкапе (status='success')."""
        stmt = (
            select(BackupRun)
            .where(BackupRun.status == "success")
            .order_by(BackupRun.finished_at.desc(), BackupRun.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_last_unreplicated_success(self) -> BackupRun | None:
        """Последняя успешная запись, которая ещё не реплицирована (replicated_at IS NULL)."""
        stmt = (
            select(BackupRun)
            .where(BackupRun.status == "success", BackupRun.replicated_at.is_(None))
            .order_by(BackupRun.finished_at.desc(), BackupRun.id.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_replicated(self, backup_id: int, replicated_at: datetime) -> None:
        """Пометить дамп как реплицированный (заполнить replicated_at)."""
        stmt = (
            update(BackupRun).where(BackupRun.id == backup_id).values(replicated_at=replicated_at)
        )
        await self._session.execute(stmt)
