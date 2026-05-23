"""Router «📋 Мои прогнозы»: активные / архив + статистика пользователя (TASK-014)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import User
from src.shared.services import EventService, PredictionService, StatsService

from .. import keyboards, texts
from ..auth import require_active_user
from ..callbacks import MyPredictionCb, MyTab, MyTabCb

__all__ = ["router"]


router = Router(name="my")

PAGE_SIZE = 7  # docs/04-bot-flows.md: «по 5–7 на страницу»


async def _build_my_view(
    user: User,
    session: AsyncSession,
    *,
    tab: MyTab,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    """Собирает (текст, клавиатуру) для текущей вкладки и страницы.

    N+1 при подгрузке `event` для каждого прогноза приемлем на MVP: PAGE_SIZE=7,
    то есть до 7 SQL-запросов. Если станет горячей точкой — добавим
    `list_*_by_user_with_relations` в репозиторий.
    """
    prediction_service = PredictionService(session)
    event_service = EventService(session)

    if tab == "active":
        fetched = await prediction_service.list_active_by_user(
            user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE + 1
        )
    else:
        fetched = await prediction_service.list_archived_by_user(
            user.id, offset=page * PAGE_SIZE, limit=PAGE_SIZE + 1
        )

    has_next = len(fetched) > PAGE_SIZE
    predictions = list(fetched[:PAGE_SIZE])
    has_prev = page > 0

    header = texts.MY_HEADER_ACTIVE if tab == "active" else texts.MY_HEADER_ARCHIVE

    pairs = []
    for prediction in predictions:
        event = await event_service.get_event(prediction.event_id, with_outcomes=True)
        if event is None:
            continue
        pairs.append((prediction, event))

    if not pairs:
        empty_text = texts.MY_NO_ACTIVE if tab == "active" else texts.MY_NO_ARCHIVE
        body = f"{header}\n\n{empty_text}"
        if tab == "archive":
            body += "\n\n" + await _format_stats(user.id, session)
        kbd = keyboards.my_predictions_kbd([], tab=tab, page=page, has_prev=False, has_next=False)
        return body, kbd

    row_lines: list[str] = []
    for prediction, event in pairs:
        outcome = next((o for o in event.outcomes if o.id == prediction.outcome_id), None)
        outcome_label = outcome.label if outcome is not None else "—"
        if tab == "active":
            row_lines.append(
                texts.MY_ROW_ACTIVE.format(
                    title=event.title,
                    starts_at=event.starts_at.strftime("%d.%m %H:%M"),
                    outcome=outcome_label,
                    close_at=event.predictions_close_at.strftime("%d.%m %H:%M"),
                )
            )
        else:
            if event.result_outcome_id is None:
                status_emoji = "⏳"
                result_label = "—"
            else:
                status_emoji = "✅" if prediction.is_correct else "❌"
                result = next((o for o in event.outcomes if o.id == event.result_outcome_id), None)
                result_label = result.label if result is not None else "—"
            row_lines.append(
                texts.MY_ROW_ARCHIVE.format(
                    title=event.title,
                    status_emoji=status_emoji,
                    starts_at=event.starts_at.strftime("%d.%m %H:%M"),
                    outcome=outcome_label,
                    result_label=result_label,
                )
            )

    body = header + "\n\n" + "\n\n".join(row_lines)
    if tab == "archive":
        body += "\n\n" + await _format_stats(user.id, session)

    events = [event for _, event in pairs]
    kbd = keyboards.my_predictions_kbd(
        events, tab=tab, page=page, has_prev=has_prev, has_next=has_next
    )
    return body, kbd


async def _format_stats(user_id: int, session: AsyncSession) -> str:
    correct, total, percent = await StatsService(session).user_stats(user_id)
    return texts.MY_STATS.format(correct=correct, total=total, percent=percent)


@router.message(Command("my"))
@router.message(F.text == "📋 Мои прогнозы")
@require_active_user
async def cmd_my(message: Message, user: User | None, session: AsyncSession) -> None:
    assert user is not None
    body, kbd = await _build_my_view(user, session, tab="active", page=0)
    await message.answer(body, reply_markup=kbd)


@router.callback_query(MyTabCb.filter())
@require_active_user
async def on_my_tab(
    query: CallbackQuery,
    callback_data: MyTabCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    assert user is not None
    body, kbd = await _build_my_view(user, session, tab=callback_data.tab, page=callback_data.page)
    if isinstance(query.message, Message):
        await query.message.edit_text(body, reply_markup=kbd)
    await query.answer()


@router.callback_query(MyPredictionCb.filter())
@require_active_user
async def on_my_prediction(
    query: CallbackQuery,
    callback_data: MyPredictionCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    assert user is not None
    # Локальный импорт против циклической зависимости с events router.
    from .events import render_event_card

    back_button: tuple[str, CallbackData] = (
        "🔙 К моим прогнозам",
        MyTabCb(tab=callback_data.tab, page=0),
    )
    await render_event_card(
        query,
        callback_data.event_id,
        back_button,
        user,
        session,
        allow_archived=callback_data.tab == "archive",
    )
