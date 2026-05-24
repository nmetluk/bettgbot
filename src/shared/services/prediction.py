"""`PredictionService` — приём и просмотр прогнозов."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import (
    EventNotPredictableError,
    OutcomeNotForEventError,
    PredictionDeadlinePassedError,
)
from ..models import Prediction
from ..repositories import EventRepository, PredictionRepository

__all__ = ["PredictionService"]


class PredictionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._predictions = PredictionRepository(session)

    async def make_prediction(self, *, user_id: int, event_id: int, outcome_id: int) -> Prediction:
        event = await self._events.get_with_outcomes(event_id)
        if event is None:
            raise EventNotPredictableError(reason="not_found")
        if event.is_archived:
            raise EventNotPredictableError(reason="archived")
        if not event.is_published:
            raise EventNotPredictableError(reason="not_published")
        if datetime.now(tz=UTC) > event.predictions_close_at:
            raise PredictionDeadlinePassedError(f"deadline for event {event_id} has passed")
        if outcome_id not in {o.id for o in event.outcomes}:
            raise OutcomeNotForEventError(
                f"outcome {outcome_id} does not belong to event {event_id}"
            )

        prediction = await self._predictions.upsert(
            user_id=user_id, event_id=event_id, outcome_id=outcome_id
        )
        await self._session.commit()
        return prediction

    async def get_user_prediction(self, user_id: int, event_id: int) -> Prediction | None:
        return await self._predictions.get_by_user_event(user_id, event_id)

    async def list_active_by_user(
        self, user_id: int, *, offset: int = 0, limit: int = 20
    ) -> Sequence[Prediction]:
        return await self._predictions.list_active_by_user(user_id, offset=offset, limit=limit)

    async def list_archived_by_user(
        self, user_id: int, *, offset: int = 0, limit: int = 20
    ) -> Sequence[Prediction]:
        return await self._predictions.list_archived_by_user(user_id, offset=offset, limit=limit)

    async def list_all_by_user_for_admin(
        self, user_id: int, *, offset: int = 0, limit: int = 100
    ) -> Sequence[Prediction]:
        """Все прогнозы пользователя (active + archived) с eager event+outcome."""
        return await self._predictions.list_all_by_user_for_admin(
            user_id, offset=offset, limit=limit
        )
