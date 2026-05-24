"""`AdminUserRepository` — запросы к таблице `admin_user`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AdminUser

__all__ = ["AdminUserRepository"]


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, admin_id: int) -> AdminUser | None:
        result = await self._session.execute(select(AdminUser).where(AdminUser.id == admin_id))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> AdminUser | None:
        result = await self._session.execute(select(AdminUser).where(AdminUser.login == login))
        return result.scalar_one_or_none()

    async def create(self, *, login: str, password_hash: str, full_name: str | None) -> AdminUser:
        admin = AdminUser(login=login, password_hash=password_hash, full_name=full_name)
        self._session.add(admin)
        await self._session.flush()
        return admin

    async def touch_last_login(self, admin_id: int) -> None:
        await self._session.execute(
            update(AdminUser).where(AdminUser.id == admin_id).values(last_login_at=func.now())
        )

    async def list_all(self) -> Sequence[AdminUser]:
        """Все админы для filter-dropdown'а audit-журнала. Сортировка по login."""
        result = await self._session.execute(select(AdminUser).order_by(AdminUser.login))
        return result.scalars().all()
