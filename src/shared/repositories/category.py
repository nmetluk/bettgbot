"""`CategoryRepository` — запросы к таблице `category`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Broadcast, Category, Event

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

    async def list_with_event_counts(
        self, *, include_inactive: bool = True
    ) -> Sequence[tuple[Category, int]]:
        """Все категории с числом ВСЕХ связанных событий (включая drafts и архив).

        Счётчик отражает реальное число строк, по которым работает FK RESTRICT
        при удалении. Для бота-side фильтра «активные опубликованные» — см.
        `EventService.list_categories_with_counts` (TASK-012).
        """
        stmt = (
            select(Category, func.count(Event.id))
            .outerjoin(Event, Event.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.sort_order, Category.id)
        )
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        result = await self._session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def count(self, *, include_inactive: bool = True) -> int:
        """Общее количество категорий."""
        stmt = select(func.count()).select_from(Category)
        if not include_inactive:
            stmt = stmt.where(Category.is_active.is_(True))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def has_events(self, category_id: int) -> bool:
        """Есть ли события, ссылающиеся на категорию (для guard delete)."""
        stmt = select(func.count(Event.id)).where(Event.category_id == category_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0) > 0

    async def has_broadcasts(self, category_id: int) -> bool:
        """Есть ли рассылки (segment=category), ссылающиеся на категорию (для guard delete)."""
        stmt = select(func.count(Broadcast.id)).where(Broadcast.category_id == category_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0) > 0
