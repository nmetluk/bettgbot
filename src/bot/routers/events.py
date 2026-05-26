"""Router «📅 Все события» — категории, список с пагинацией, карточка (TASK-012/013)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import User
from src.shared.services import CategoryService, EventService, PredictionService

from .. import keyboards, texts
from .._text_safety import safe_format
from ..auth import require_active_user
from ..callbacks import CategoryCb, CategoryListCb, EventCb

__all__ = ["render_event_card", "router"]


router = Router(name="events")

PAGE_SIZE = 7  # docs/04-bot-flows.md: «по 5–7 на страницу»


@router.message(Command("events"))
@router.message(F.text == "📅 Все события")
@require_active_user
async def cmd_events(message: Message, user: User | None, session: AsyncSession) -> None:
    service = EventService(session)
    cats, total = await service.list_categories_with_counts()
    if total == 0:
        await message.answer(texts.NO_EVENTS_AT_ALL, reply_markup=keyboards.main_menu())
        return

    await message.answer(
        texts.CATEGORIES_PROMPT,
        reply_markup=keyboards.categories_kbd(cats, total),
    )


@router.callback_query(CategoryListCb.filter())
@require_active_user
async def on_back_to_categories(
    query: CallbackQuery, user: User | None, session: AsyncSession
) -> None:
    service = EventService(session)
    cats, total = await service.list_categories_with_counts()
    if isinstance(query.message, Message):
        await query.message.edit_text(
            texts.CATEGORIES_PROMPT,
            reply_markup=keyboards.categories_kbd(cats, total),
        )
    await query.answer()


@router.callback_query(CategoryCb.filter())
@require_active_user
async def on_category(
    query: CallbackQuery,
    callback_data: CategoryCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    service = EventService(session)
    page = callback_data.page
    # +1 чтобы понять, есть ли следующая страница, без отдельного count.
    fetched = await service.list_active(
        category_id=callback_data.category_id,
        offset=page * PAGE_SIZE,
        limit=PAGE_SIZE + 1,
    )
    events = list(fetched[:PAGE_SIZE])
    has_next = len(fetched) > PAGE_SIZE
    has_prev = page > 0

    if not events:
        if isinstance(query.message, Message):
            await query.message.edit_text(
                texts.NO_EVENTS_IN_CATEGORY,
                reply_markup=keyboards.events_in_category_kbd(
                    [],
                    page=page,
                    has_prev=False,
                    has_next=False,
                    category_id=callback_data.category_id,
                ),
            )
        await query.answer()
        return

    category_name = "Все категории"
    if callback_data.category_id is not None:
        cat = await CategoryService(session).get_by_id(callback_data.category_id)
        if cat is not None:
            category_name = cat.name

    title = f"<b>{category_name}</b> — страница {page + 1}"
    if isinstance(query.message, Message):
        await query.message.edit_text(
            title,
            reply_markup=keyboards.events_in_category_kbd(
                events,
                page=page,
                has_prev=has_prev,
                has_next=has_next,
                category_id=callback_data.category_id,
            ),
        )
    await query.answer()


async def render_event_card(
    query: CallbackQuery,
    event_id: int,
    back_button: tuple[str, CallbackData],
    user: User,
    session: AsyncSession,
    *,
    allow_archived: bool = False,
) -> None:
    """Собирает текст карточки + клавиатуру и редактирует сообщение.

    Используется в `on_event` (callback из списка событий), `on_predict_cancel`
    (отмена FSM) и `on_my_prediction` (тап из «Мои прогнозы»). `back_button` —
    пара `(text, CallbackData)`: позволяет каждой входной точке задать свою
    кнопку возврата без знания о других сценариях.

    `allow_archived=True` — для входа из «Мои прогнозы → Архив»: показываем
    карточку даже если событие архивно. Кнопки «Сделать прогноз» не появится,
    потому что `predictions_close_at` уже прошёл (`can_predict` будет False).
    """
    service = EventService(session)
    event = await service.get_event(event_id, with_outcomes=True)
    if event is None or not event.is_published:
        await query.answer(texts.EVENT_NOT_AVAILABLE, show_alert=True)
        return
    if event.is_archived and not allow_archived:
        await query.answer(texts.EVENT_NOT_AVAILABLE, show_alert=True)
        return

    category = await CategoryService(session).get_by_id(event.category_id)
    category_name = category.name if category is not None else "Без категории"

    description_block = f"\n\n{event.description}" if event.description else ""
    outcomes_lines = [f"{i + 1}) {outcome.label}" for i, outcome in enumerate(event.outcomes)]
    outcomes_block = "\n".join(outcomes_lines)

    existing = await PredictionService(session).get_user_prediction(user.id, event.id)
    prediction_block = ""
    if existing is not None:
        chosen = next((o for o in event.outcomes if o.id == existing.outcome_id), None)
        if chosen is not None:
            prediction_block = f"\n\n✅ Ваш прогноз: «{chosen.label}»"

    text = safe_format(
        texts.EVENT_CARD,
        category_name=category_name,
        title=event.title,
        description_block=description_block,
        starts_at_fmt=event.starts_at.strftime("%d.%m.%Y %H:%M"),
        close_at_fmt=event.predictions_close_at.strftime("%d.%m %H:%M"),
        outcomes_block=outcomes_block,
        prediction_block=prediction_block,
    )

    can_predict = event.predictions_close_at > datetime.now(tz=UTC)

    if isinstance(query.message, Message):
        await query.message.edit_text(
            text,
            reply_markup=keyboards.event_card_kbd(
                event_id=event.id,
                back_button=back_button,
                can_predict=can_predict,
                has_prediction=existing is not None,
                predict_back_category_id=event.category_id,
            ),
        )
    await query.answer()


@router.callback_query(EventCb.filter())
@require_active_user
async def on_event(
    query: CallbackQuery,
    callback_data: EventCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    # После @require_active_user user не None; mypy не сужает, дадим явный assert.
    assert user is not None
    back_button: tuple[str, CallbackData] = (
        "🔙 К событиям",
        CategoryCb(category_id=callback_data.back_category_id, page=0),
    )
    await render_event_card(query, callback_data.event_id, back_button, user, session)
