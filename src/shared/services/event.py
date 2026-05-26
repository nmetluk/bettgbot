"""`EventService` — создание/публикация/архивация событий, фиксация итога."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import (
    EventAlreadyHasResultError,
    EventNotEnoughOutcomesError,
    EventNotFoundError,
    OutcomeInUseError,
    OutcomeNotForEventError,
)
from ..models import Category, Event, Outcome
from ..repositories import (
    AuditLogRepository,
    EventRepository,
    OutcomeRepository,
    PredictionRepository,
)
from ..repositories.event import AdminEventPeriod, AdminEventStatus

__all__ = ["EventService"]


class EventService:
    """Доменная логика управления событиями."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._outcomes = OutcomeRepository(session)
        self._predictions = PredictionRepository(session)
        self._audit = AuditLogRepository(session)

    # -- write --

    async def create_event(
        self,
        *,
        category_id: int,
        title: str,
        description: str | None,
        metadata: dict[str, Any] | None,
        starts_at: datetime,
        predictions_close_at: datetime,
        by_admin_id: int,
    ) -> Event:
        event = await self._events.create(
            category_id=category_id,
            title=title,
            description=description,
            metadata=metadata,
            starts_at=starts_at,
            predictions_close_at=predictions_close_at,
            created_by_admin_id=by_admin_id,
        )
        await self._audit.add(
            admin_id=by_admin_id,
            action="event.create",
            payload={
                "event_id": event.id,
                "title": title,
                "category_id": category_id,
            },
        )
        await self._session.commit()
        return event

    async def update_event(self, event_id: int, by_admin_id: int, **fields: Any) -> None:
        await self._events.update(event_id, **fields)
        await self._audit.add(
            admin_id=by_admin_id,
            action="event.update",
            payload={"event_id": event_id, "fields": list(fields.keys())},
        )
        await self._session.commit()

    async def publish_event(self, event_id: int, by_admin_id: int) -> None:
        event = await self._events.get_by_id(event_id)
        if event is None:
            raise EventNotFoundError(f"event {event_id} not found")

        outcomes_count = await self._outcomes.count_by_event(event_id)
        if outcomes_count < 2:
            raise EventNotEnoughOutcomesError(
                f"event {event_id} has {outcomes_count} outcomes; need at least 2"
            )

        await self._events.set_published(event_id, True)
        await self._audit.add(
            admin_id=by_admin_id,
            action="event.publish",
            payload={"event_id": event_id},
        )
        await self._session.commit()

    async def unpublish_event(self, event_id: int, by_admin_id: int) -> None:
        event = await self._events.get_by_id(event_id)
        if event is None:
            raise EventNotFoundError(f"event {event_id} not found")
        await self._events.set_published(event_id, False)
        await self._audit.add(
            admin_id=by_admin_id,
            action="event.unpublish",
            payload={"event_id": event_id},
        )
        await self._session.commit()

    async def set_result(self, event_id: int, outcome_id: int, by_admin_id: int) -> int:
        event = await self._events.get_with_outcomes(event_id)
        if event is None:
            raise EventNotFoundError(f"event {event_id} not found")

        if event.result_outcome_id is not None:
            raise EventAlreadyHasResultError(
                f"event {event_id} already has result {event.result_outcome_id}"
            )

        if outcome_id not in {o.id for o in event.outcomes}:
            raise OutcomeNotForEventError(
                f"outcome {outcome_id} does not belong to event {event_id}"
            )

        archived_at = datetime.now(tz=UTC)
        await self._events.set_result(event_id, outcome_id, archived_at)
        marked = await self._predictions.mark_correctness(event_id, outcome_id)
        await self._audit.add(
            admin_id=by_admin_id,
            action="event.set_result",
            payload={
                "event_id": event_id,
                "outcome_id": outcome_id,
                "marked": marked,
            },
        )
        await self._session.commit()
        return marked

    async def archive_stale_events(
        self, *, now: datetime | None = None, threshold_days: int = 7
    ) -> int:
        """Архивирует события без итога, у которых `starts_at < now - threshold_days`.

        Возвращает количество архивированных. Это страховка от ситуации, когда
        админ забыл зафиксировать итог: чтобы такие события не висели в каталоге
        бесконечно, через N дней их прячем в архив (без `result_outcome_id`).
        Прогнозы по ним остаются с `is_correct = NULL`. Audit-лог не пишем —
        автоматическое действие без `admin_id`.
        """
        if now is None:
            now = datetime.now(tz=UTC)
        cutoff = now - timedelta(days=threshold_days)
        archived_count = await self._events.archive_stale(cutoff=cutoff)
        if archived_count > 0:
            await self._session.commit()
        return archived_count

    async def add_outcome(
        self,
        *,
        event_id: int,
        label: str,
        sort_order: int = 0,
        by_admin_id: int,
    ) -> Outcome:
        outcome = await self._outcomes.create(event_id=event_id, label=label, sort_order=sort_order)
        await self._audit.add(
            admin_id=by_admin_id,
            action="outcome.create",
            payload={"outcome_id": outcome.id, "event_id": event_id, "label": label},
        )
        await self._session.commit()
        return outcome

    async def update_outcome(self, outcome_id: int, event_id: int, by_admin_id: int, **fields: Any) -> None:
        affected = await self._outcomes.update(outcome_id, event_id, **fields)
        if affected == 0:
            raise OutcomeNotForEventError(event_id, outcome_id)
        await self._audit.add(
            admin_id=by_admin_id,
            action="outcome.update",
            payload={"outcome_id": outcome_id, "fields": list(fields.keys())},
        )
        await self._session.commit()

    async def delete_outcome(self, outcome_id: int, event_id: int, by_admin_id: int) -> None:
        try:
            affected = await self._outcomes.delete(outcome_id, event_id)
            if affected == 0:
                raise OutcomeNotForEventError(event_id, outcome_id)
            await self._audit.add(
                admin_id=by_admin_id,
                action="outcome.delete",
                payload={"outcome_id": outcome_id},
            )
            await self._session.commit()
        except IntegrityError as exc:
            raise OutcomeInUseError(f"outcome {outcome_id} has predictions; cannot delete") from exc

    # -- read --

    async def get_event(
        self,
        event_id: int,
        *,
        with_outcomes: bool = False,
        with_result: bool = False,
    ) -> Event | None:
        if with_outcomes:
            return await self._events.get_with_outcomes(event_id)
        if with_result:
            return await self._events.get_with_result(event_id)
        return await self._events.get_by_id(event_id)

    async def list_active(
        self, *, category_id: int | None = None, offset: int = 0, limit: int = 20
    ) -> Sequence[Event]:
        return await self._events.list_active(category_id=category_id, offset=offset, limit=limit)

    async def count_active(self, *, category_id: int | None = None) -> int:
        return await self._events.count_active(category_id=category_id)

    async def list_for_admin(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[Event]:
        return await self._events.list_for_admin(
            category_id=category_id, status=status, offset=offset, limit=limit
        )

    async def count_for_admin(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
    ) -> int:
        return await self._events.count_for_admin(category_id=category_id, status=status)

    async def list_admin_with_counts(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        period: AdminEventPeriod = "all",
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[tuple[Event, int]]:
        return await self._events.list_for_admin_with_predictions_count(
            category_id=category_id,
            status=status,
            period=period,
            offset=offset,
            limit=limit,
        )

    async def count_admin(
        self,
        *,
        category_id: int | None = None,
        status: AdminEventStatus = "all",
        period: AdminEventPeriod = "all",
    ) -> int:
        return await self._events.count_for_admin_with_period(
            category_id=category_id, status=status, period=period
        )

    async def list_categories_with_counts(
        self,
    ) -> tuple[Sequence[tuple[Category, int]], int]:
        """Возвращает `(список (категория, число активных событий), всего активных)`.

        «Активное» = `is_published AND NOT is_archived`. Категории с нулём
        активных событий — включаются (UX показывает «событий пока нет»).
        """
        count_expr = func.count(Event.id).filter(
            Event.is_published.is_(True), Event.is_archived.is_(False)
        )
        stmt = (
            select(Category, count_expr)
            .outerjoin(Event, Event.category_id == Category.id)
            .where(Category.is_active.is_(True))
            .group_by(Category.id)
            .order_by(Category.sort_order, Category.id)
        )
        result = await self._session.execute(stmt)
        rows = [(row[0], int(row[1])) for row in result.all()]
        total = sum(count for _, count in rows)
        return rows, total
