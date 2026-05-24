"""`EventRepository` — запросы к таблице `event`. Не управляет транзакциями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Event, Prediction

__all__ = ["AdminEventPeriod", "AdminEventStatus", "EventRepository"]

AdminEventStatus = Literal["all", "draft", "published_open", "published_closed", "archived"]
AdminEventPeriod = Literal["all", "next7", "past"]


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, event_id: int) -> Event | None:
        result = await self._session.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def get_with_outcomes(self, event_id: int) -> Event | None:
        stmt = select(Event).options(selectinload(Event.outcomes)).where(Event.id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_result(self, event_id: int) -> Event | None:
        stmt = select(Event).options(selectinload(Event.result_outcome)).where(Event.id == event_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _active_filters(self, category_id: int | None) -> list:  # type: ignore[type-arg]
        clauses: list = [  # type: ignore[type-arg]
            Event.is_published.is_(True),
            Event.is_archived.is_(False),
        ]
        if category_id is not None:
            clauses.append(Event.category_id == category_id)
        return clauses

    async def list_active(
        self,
        *,
        category_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[Event]:
        stmt = (
            select(Event)
            .where(*self._active_filters(category_id))
            .order_by(Event.starts_at, Event.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_active(self, *, category_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(Event).where(*self._active_filters(category_id))
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    def _admin_filters(self, category_id: int | None, status: AdminEventStatus) -> list:  # type: ignore[type-arg]
        clauses: list = []  # type: ignore[type-arg]
        if category_id is not None:
            clauses.append(Event.category_id == category_id)
        now = func.now()
        if status == "draft":
            clauses.append(Event.is_published.is_(False))
            clauses.append(Event.is_archived.is_(False))
        elif status == "published_open":
            clauses.append(Event.is_published.is_(True))
            clauses.append(Event.is_archived.is_(False))
            clauses.append(Event.predictions_close_at > now)
        elif status == "published_closed":
            clauses.append(Event.is_published.is_(True))
            clauses.append(Event.is_archived.is_(False))
            clauses.append(Event.predictions_close_at <= now)
        elif status == "archived":
            clauses.append(Event.is_archived.is_(True))
        # status == "all" — без фильтра по статусу
        return clauses

    async def list_for_admin(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Event]:
        stmt = (
            select(Event)
            .where(*self._admin_filters(category_id, status))
            .order_by(Event.starts_at.desc(), Event.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_for_admin(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
    ) -> int:
        stmt = (
            select(func.count()).select_from(Event).where(*self._admin_filters(category_id, status))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def create(
        self,
        *,
        category_id: int,
        title: str,
        description: str | None,
        metadata: dict[str, Any] | None,
        starts_at: datetime,
        predictions_close_at: datetime,
        created_by_admin_id: int,
    ) -> Event:
        event = Event(
            category_id=category_id,
            title=title,
            description=description,
            metadata_=metadata if metadata is not None else {},
            starts_at=starts_at,
            predictions_close_at=predictions_close_at,
            created_by_admin_id=created_by_admin_id,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def update(self, event_id: int, **fields: Any) -> None:
        if not fields:
            return
        await self._session.execute(update(Event).where(Event.id == event_id).values(**fields))

    async def set_published(self, event_id: int, published: bool) -> None:
        await self._session.execute(
            update(Event).where(Event.id == event_id).values(is_published=published)
        )

    async def set_result(self, event_id: int, outcome_id: int, archived_at: datetime) -> None:
        await self._session.execute(
            update(Event)
            .where(Event.id == event_id)
            .values(
                result_outcome_id=outcome_id,
                is_archived=True,
                archived_at=archived_at,
            )
        )

    async def archive_stale(self, *, cutoff: datetime) -> int:
        """Bulk-update: помечает `is_archived=true, archived_at=now()` события без итога,
        у которых `starts_at < cutoff`.

        Returns: количество затронутых строк.
        """
        stmt = (
            update(Event)
            .where(
                Event.starts_at < cutoff,
                Event.result_outcome_id.is_(None),
                Event.is_archived.is_(False),
            )
            .values(is_archived=True, archived_at=func.now())
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    def _period_filters(self, period: AdminEventPeriod) -> list:  # type: ignore[type-arg]
        clauses: list = []  # type: ignore[type-arg]
        if period == "next7":
            now = datetime.now(tz=UTC)
            clauses.append(Event.starts_at >= now)
            clauses.append(Event.starts_at < now + timedelta(days=7))
        elif period == "past":
            clauses.append(Event.starts_at < datetime.now(tz=UTC))
        # "all" — no extra filter
        return clauses

    async def list_for_admin_with_predictions_count(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        period: AdminEventPeriod = "all",
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[tuple[Event, int]]:
        """Список событий для admin-таблицы с подсчётом прогнозов.

        Один SQL: LEFT JOIN prediction + GROUP BY event.id + COUNT. Фильтры
        status (`all/draft/published_*/archived`) и period (`all/next7/past`)
        через WHERE. `joinedload(Category)` — чтобы в шаблоне показать имя
        категории, не +N запросов.
        """
        # selectinload вместо joinedload — joinedload в одном запросе с GROUP BY
        # требует все Category-колонки в GROUP BY; selectinload делает один
        # отдельный SELECT по collected category_ids. На admin-странице ОК.
        stmt = (
            select(Event, func.count(Prediction.id))
            .outerjoin(Prediction, Prediction.event_id == Event.id)
            .options(selectinload(Event.category))
            .group_by(Event.id)
            .where(
                *self._admin_filters(category_id, status),
                *self._period_filters(period),
            )
            .order_by(Event.starts_at.desc(), Event.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], int(row[1])) for row in result.all()]

    async def count_for_admin_with_period(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        period: AdminEventPeriod = "all",
    ) -> int:
        """Count с теми же фильтрами для пагинации."""
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(
                *self._admin_filters(category_id, status),
                *self._period_filters(period),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_with_deadline_in_window(
        self, *, since: datetime, until: datetime
    ) -> Sequence[Event]:
        stmt = (
            select(Event)
            .where(
                and_(
                    Event.is_published.is_(True),
                    Event.is_archived.is_(False),
                    Event.predictions_close_at >= since,
                    Event.predictions_close_at <= until,
                )
            )
            .order_by(Event.predictions_close_at, Event.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
