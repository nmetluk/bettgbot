"""`AuditLogRepository` — запросы к таблице `audit_log`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

__all__ = ["AuditLogRepository"]


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, *, admin_id: int, action: str, payload: dict[str, Any]) -> AuditLog:
        entry = AuditLog(admin_id=admin_id, action=action, payload=payload)
        self._session.add(entry)
        await self._session.flush()
        return entry

    def _filters(
        self,
        admin_id: int | None,
        action: str | None,
        since: datetime | None,
        until: datetime | None,
    ) -> list:  # type: ignore[type-arg]
        clauses: list = []  # type: ignore[type-arg]
        if admin_id is not None:
            clauses.append(AuditLog.admin_id == admin_id)
        if action is not None:
            clauses.append(AuditLog.action == action)
        if since is not None:
            clauses.append(AuditLog.created_at >= since)
        if until is not None:
            clauses.append(AuditLog.created_at <= until)
        return clauses

    async def list(
        self,
        *,
        admin_id: int | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(*self._filters(admin_id, action, since, until))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        *,
        admin_id: int | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AuditLog)
            .where(*self._filters(admin_id, action, since, until))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
