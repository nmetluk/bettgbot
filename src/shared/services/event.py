"""`EventService` — создание/публикация/архивация событий, фиксация итога."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import (
    EventAlreadyHasResultError,
    EventNotEnoughOutcomesError,
    EventNotFoundError,
    OutcomeInUseError,
    OutcomeNotForEventError,
)
from ..models import Event, Outcome
from ..repositories import (
    AuditLogRepository,
    EventRepository,
    OutcomeRepository,
    PredictionRepository,
)
from ..repositories.event import AdminEventStatus

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

    async def update_outcome(self, outcome_id: int, by_admin_id: int, **fields: Any) -> None:
        await self._outcomes.update(outcome_id, **fields)
        await self._audit.add(
            admin_id=by_admin_id,
            action="outcome.update",
            payload={"outcome_id": outcome_id, "fields": list(fields.keys())},
        )
        await self._session.commit()

    async def delete_outcome(self, outcome_id: int, by_admin_id: int) -> None:
        try:
            await self._outcomes.delete(outcome_id)
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
