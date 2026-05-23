"""`AuditService` — точка входа в audit-журнал из admin-UI.

Внутри других сервисов запись делается напрямую через `AuditLogRepository`,
чтобы не плодить инстансы и не путать транзакционные границы. `AuditService.add`
не делает commit — caller-сервис управляет транзакцией.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog
from ..repositories import AuditLogRepository

__all__ = ["AuditService"]


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditLogRepository(session)

    async def add(self, *, admin_id: int, action: str, payload: dict[str, Any]) -> AuditLog:
        return await self._audit.add(admin_id=admin_id, action=action, payload=payload)

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
        return await self._audit.list(
            admin_id=admin_id,
            action=action,
            since=since,
            until=until,
            offset=offset,
            limit=limit,
        )

    async def count(
        self,
        *,
        admin_id: int | None = None,
        action: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        return await self._audit.count(admin_id=admin_id, action=action, since=since, until=until)
