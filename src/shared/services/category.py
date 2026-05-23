"""`CategoryService` — read-only обёртка над `CategoryRepository` для бота.

CRUD-операции (create/update/delete) появятся в TASK-021 (admin категории).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Category
from ..repositories import CategoryRepository

__all__ = ["CategoryService"]


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._categories = CategoryRepository(session)

    async def get_by_id(self, category_id: int) -> Category | None:
        return await self._categories.get_by_id(category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        return await self._categories.get_by_slug(slug)

    async def list_active(self) -> Sequence[Category]:
        return await self._categories.list(active_only=True)
