"""`UserRepository` — запросы к таблице `user`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User

__all__ = ["UserRepository"]


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_tg_user_id(self, tg_user_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.tg_user_id == tg_user_id))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self._session.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        tg_user_id: int,
        phone: str,
        tg_username: str | None,
        first_name: str,
        last_name: str | None,
    ) -> User:
        user = User(
            tg_user_id=tg_user_id,
            phone=phone,
            tg_username=tg_username,
            first_name=first_name,
            last_name=last_name,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def touch_last_seen(self, user_id: int) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(last_seen_at=func.now())
        )

    async def set_blocked(self, user_id: int, blocked: bool) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(is_blocked=blocked)
        )

    def _admin_filter(self, query: str | None) -> list:  # type: ignore[type-arg]
        if not query:
            return []
        pattern = f"%{query}%"
        return [
            or_(
                User.phone.ilike(pattern),
                User.tg_username.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
        ]

    async def list_for_admin(
        self,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[User]:
        stmt = (
            select(User)
            .where(*self._admin_filter(query))
            .order_by(User.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(self, *, query: str | None = None) -> int:
        stmt = select(func.count()).select_from(User).where(*self._admin_filter(query))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
