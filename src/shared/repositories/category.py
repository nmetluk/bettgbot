"""`CategoryRepository` — запросы к таблице `category`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Category

__all__ = ["CategoryRepository"]


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, category_id: int) -> Category | None:
        result = await self._session.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Category | None:
        result = await self._session.execute(select(Category).where(Category.slug == slug))
        return result.scalar_one_or_none()

    async def list(self, *, active_only: bool = False) -> Sequence[Category]:
        stmt = select(Category)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        stmt = stmt.order_by(Category.sort_order, Category.id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        *,
        name: str,
        slug: str,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Category:
        category = Category(name=name, slug=slug, sort_order=sort_order, is_active=is_active)
        self._session.add(category)
        await self._session.flush()
        return category

    async def update(self, category_id: int, **fields: Any) -> None:
        if not fields:
            return
        await self._session.execute(
            update(Category).where(Category.id == category_id).values(**fields)
        )

    async def delete(self, category_id: int) -> None:
        await self._session.execute(delete(Category).where(Category.id == category_id))
