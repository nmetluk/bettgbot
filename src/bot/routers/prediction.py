"""Router `/predict` и FSM `MakingPrediction` (TASK-013)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.exceptions import (
    EventNotPredictableError,
    OutcomeNotForEventError,
    PredictionDeadlinePassedError,
)
from src.shared.logging import get_logger
from src.shared.models import User
from src.shared.services import EventService, PredictionService

from .. import keyboards, texts
from .._text_safety import safe_format
from ..auth import require_active_user
from ..callbacks import (
    CategoryCb,
    PredictCancelCb,
    PredictConfirmCb,
    PredictPickCb,
    PredictStartCb,
)
from ..states import MakingPrediction

__all__ = ["router"]


logger = get_logger(__name__)

router = Router(name="prediction")


@router.message(Command("predict"))
@router.message(F.text == "🎯 Сделать прогноз")
@require_active_user
async def cmd_predict(
    message: Message,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Из главного меню — перенаправление в каталог. Карточка события → FSM."""
    await state.clear()
    # Локальный импорт, чтобы избежать круговой зависимости с events router.
    from .events import cmd_events

    await cmd_events(message, user=user, session=session)


@router.callback_query(PredictStartCb.filter())
@require_active_user
async def on_predict_start(
    query: CallbackQuery,
    callback_data: PredictStartCb,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)
    if event is None or event.is_archived or not event.is_published:
        await query.answer(texts.EVENT_NOT_AVAILABLE, show_alert=True)
        await state.clear()
        return
    if event.predictions_close_at <= datetime.now(tz=UTC):
        await query.answer(texts.PREDICT_DEADLINE_PASSED, show_alert=True)
        await state.clear()
        return

    await state.set_state(MakingPrediction.choosing_outcome)
    await state.update_data(event_id=event.id, back_category_id=callback_data.back_category_id)

    text = safe_format(texts.PREDICT_PICK_OUTCOME, title=event.title)
    if isinstance(query.message, Message):
        await query.message.edit_text(
            text,
            reply_markup=keyboards.predict_outcomes_kbd(
                event.id, event.outcomes, callback_data.back_category_id
            ),
        )
    await query.answer()


@router.callback_query(PredictPickCb.filter(), MakingPrediction.choosing_outcome)
@require_active_user
async def on_predict_pick(
    query: CallbackQuery,
    callback_data: PredictPickCb,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)
    if event is None or event.is_archived or not event.is_published:
        await query.answer(texts.EVENT_NOT_AVAILABLE, show_alert=True)
        await state.clear()
        return
    if event.predictions_close_at <= datetime.now(tz=UTC):
        await query.answer(texts.PREDICT_DEADLINE_PASSED, show_alert=True)
        await state.clear()
        return

    outcome = next((o for o in event.outcomes if o.id == callback_data.outcome_id), None)
    if outcome is None:
        await query.answer(texts.PREDICT_OUTCOME_NOT_FOUND, show_alert=True)
        await state.clear()
        return

    await state.set_state(MakingPrediction.confirming)
    data = await state.get_data()
    back_category_id = data.get("back_category_id")

    text = safe_format(
        texts.PREDICT_CONFIRM,
        label=outcome.label,
        close_at_fmt=event.predictions_close_at.strftime("%d.%m %H:%M"),
    )
    if isinstance(query.message, Message):
        await query.message.edit_text(
            text,
            reply_markup=keyboards.predict_confirm_kbd(event.id, outcome.id, back_category_id),
        )
    await query.answer()


@router.callback_query(PredictConfirmCb.filter(), MakingPrediction.confirming)
@require_active_user
async def on_predict_confirm(
    query: CallbackQuery,
    callback_data: PredictConfirmCb,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    assert user is not None  # после @require_active_user
    service = PredictionService(session)
    existing = await service.get_user_prediction(user.id, callback_data.event_id)
    was_new = existing is None

    try:
        prediction = await service.make_prediction(
            user_id=user.id,
            event_id=callback_data.event_id,
            outcome_id=callback_data.outcome_id,
        )
        event = await EventService(session).get_event(callback_data.event_id, with_outcomes=True)
        assert event is not None  # успешный make_prediction гарантирует существование
        outcome = next(o for o in event.outcomes if o.id == prediction.outcome_id)

        template = texts.PREDICT_SAVED if was_new else texts.PREDICT_UPDATED
        text = safe_format(template, label=outcome.label)
        if isinstance(query.message, Message):
            await query.message.edit_text(text)
        logger.info(
            "bot.predict.saved",
            user_id=user.id,
            event_id=event.id,
            outcome_id=outcome.id,
            was_new=was_new,
        )
        await query.answer()
    except EventNotPredictableError as exc:
        await query.answer(texts.PREDICT_EVENT_UNAVAILABLE, show_alert=True)
        logger.info(
            "bot.predict.event_unavailable",
            user_id=user.id,
            event_id=callback_data.event_id,
            reason=exc.reason,
        )
    except PredictionDeadlinePassedError:
        await query.answer(texts.PREDICT_DEADLINE_PASSED, show_alert=True)
    except OutcomeNotForEventError:
        await query.answer(texts.PREDICT_OUTCOME_NOT_FOUND, show_alert=True)
    finally:
        await state.clear()


@router.callback_query(PredictCancelCb.filter())
@require_active_user
async def on_predict_cancel(
    query: CallbackQuery,
    callback_data: PredictCancelCb,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    assert user is not None
    await state.clear()
    from .events import render_event_card

    back_button: tuple[str, CallbackData] = (
        "🔙 К событиям",
        CategoryCb(category_id=callback_data.back_category_id, page=0),
    )
    await render_event_card(query, callback_data.event_id, back_button, user, session)


# Fallback: callback приходит без подходящего state (например, после рестарта бота
# или из старого сообщения). Регистрируется ПОСЛЕ stateful-версий — aiogram
# проверяет handler'ы по порядку и stateful совпадает первым, если state есть.
@router.callback_query(PredictPickCb.filter())
async def on_predict_pick_no_state(query: CallbackQuery) -> None:
    await query.answer(texts.PREDICT_EVENT_UNAVAILABLE, show_alert=True)


@router.callback_query(PredictConfirmCb.filter())
async def on_predict_confirm_no_state(query: CallbackQuery) -> None:
    await query.answer(texts.PREDICT_EVENT_UNAVAILABLE, show_alert=True)
