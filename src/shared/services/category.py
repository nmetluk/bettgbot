"""`CategoryService` — read + CRUD-обёртка над `CategoryRepository`.

CRUD-методы (`create_category`, `update_category`, `delete_category`) появились
в TASK-021 для админки. Пишут в audit-лог, оборачивают `IntegrityError`
в доменные исключения (`CategorySlugConflictError`, `CategoryHasEventsError`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import (
    CategoryHasEventsError,
    CategoryNotFoundError,
    CategorySlugConflictError,
)
from ..models import Category
from ..repositories import AuditLogRepository, CategoryRepository

__all__ = ["CategoryService"]


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._categories = CategoryRepository(session)
        self._audit = AuditLogRepository(session)

    # --- read ---

    async def get_by_id(self, category_id: int) -> Category | None:
        return await self._categories.get_by_id(category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        return await self._categories.get_by_slug(slug)

    async def list_active(self) -> Sequence[Category]:
        return await self._categories.list(active_only=True)

    async def list_all_with_counts(
        self, *, include_inactive: bool = True
    ) -> Sequence[tuple[Category, int]]:
        return await self._categories.list_with_event_counts(include_inactive=include_inactive)

    # --- write (admin) ---

    async def create_category(
        self,
        *,
        name: str,
        slug: str,
        sort_order: int = 0,
        is_active: bool = True,
        by_admin_id: int,
    ) -> Category:
        try:
            category = await self._categories.create(
                name=name, slug=slug, sort_order=sort_order, is_active=is_active
            )
            await self._audit.add(
                admin_id=by_admin_id,
                action="category.create",
                payload={
                    "category_id": category.id,
                    "name": name,
                    "slug": slug,
                },
            )
            await self._session.commit()
            return category
        except IntegrityError as exc:
            raise CategorySlugConflictError(slug) from exc

    async def update_category(
        self,
        category_id: int,
        *,
        by_admin_id: int,
        **fields: Any,
    ) -> None:
        existing = await self._categories.get_by_id(category_id)
        if existing is None:
            raise CategoryNotFoundError(category_id)

        if not fields:
            return

        try:
            await self._categories.update(category_id, **fields)
            await self._audit.add(
                admin_id=by_admin_id,
                action="category.update",
                payload={"category_id": category_id, "fields": list(fields.keys())},
            )
            await self._session.commit()
        except IntegrityError as exc:
            raise CategorySlugConflictError(slug=fields.get("slug", existing.slug)) from exc

    async def delete_category(self, category_id: int, *, by_admin_id: int) -> None:
        existing = await self._categories.get_by_id(category_id)
        if existing is None:
            raise CategoryNotFoundError(category_id)

        try:
            await self._categories.delete(category_id)
            await self._audit.add(
                admin_id=by_admin_id,
                action="category.delete",
                payload={"category_id": category_id, "name": existing.name},
            )
            await self._session.commit()
        except IntegrityError as exc:
            raise CategoryHasEventsError(category_id) from exc
