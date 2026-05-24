"""Router `/reminders` — настройка напоминаний (TASK-015)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.exceptions import InvalidReminderOffsetsError
from src.shared.logging import get_logger
from src.shared.models import ReminderSetting, User
from src.shared.services import ReminderService

from .. import keyboards, texts
from .._reminders_parser import parse_offset
from ..auth import require_active_user
from ..callbacks import (
    AddOffsetCb,
    CustomOffsetCb,
    PresetOffsetCb,
    RemindersMenuCb,
    RemoveOffsetCb,
    ToggleRemindersCb,
)
from ..states import EditingReminders

__all__ = ["router"]


logger = get_logger(__name__)

router = Router(name="reminders")


def _format_menu_text(setting: ReminderSetting) -> str:
    parts: list[str] = [texts.REMINDERS_HEADER]
    if setting.enabled:
        parts.append(texts.REMINDERS_STATUS_ENABLED)
        if setting.offsets_minutes:
            sorted_offsets = sorted(setting.offsets_minutes, reverse=True)
            lines = [f"• {keyboards.humanize_minutes(m)}" for m in sorted_offsets]
            parts.append(texts.REMINDERS_LIST_HEADER + "\n" + "\n".join(lines))
        else:
            parts.append(texts.REMINDERS_LIST_EMPTY)
    else:
        parts.append(texts.REMINDERS_STATUS_DISABLED)
        parts.append(texts.REMINDERS_HINT_DISABLED)
    return "\n\n".join(parts)


def _format_error(exc: InvalidReminderOffsetsError) -> str:
    """Превращает текст исключения в человекочитаемую константу."""
    message = str(exc)
    if "too many" in message:
        return texts.REMINDERS_ERR_TOO_MANY
    if "duplicate" in message:
        return texts.REMINDERS_ERR_DUPLICATE
    if "below minimum" in message:
        return texts.REMINDERS_ERR_BELOW_MINIMUM
    # Fallback на общий «не понял ввод» — иначе показали бы пустую алертку.
    return texts.REMINDERS_INVALID_INPUT


async def _render_menu_edit(query: CallbackQuery, setting: ReminderSetting) -> None:
    if isinstance(query.message, Message):
        await query.message.edit_text(
            _format_menu_text(setting),
            reply_markup=keyboards.reminders_menu_kbd(setting),
        )
    await query.answer()


@router.message(Command("reminders"))
@router.message(F.text == "🔔 Напоминания")
@require_active_user
async def cmd_reminders(
    message: Message,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    assert user is not None
    # Сброс FSM на случай, если пользователь застрял в `adding_offset` и решил
    # начать заново через команду — аналог поведения `cmd_start`.
    await state.clear()
    service = ReminderService(session)
    setting = await service.get(user.id)
    assert setting is not None  # инвариант от UserService.register_or_authenticate
    await message.answer(
        _format_menu_text(setting),
        reply_markup=keyboards.reminders_menu_kbd(setting),
    )


@router.callback_query(RemindersMenuCb.filter())
@require_active_user
async def on_reminders_menu(query: CallbackQuery, user: User | None, session: AsyncSession) -> None:
    assert user is not None
    setting = await ReminderService(session).get(user.id)
    assert setting is not None
    await _render_menu_edit(query, setting)


@router.callback_query(ToggleRemindersCb.filter())
@require_active_user
async def on_toggle_reminders(
    query: CallbackQuery, user: User | None, session: AsyncSession
) -> None:
    assert user is not None
    service = ReminderService(session)
    setting = await service.get(user.id)
    assert setting is not None
    await service.update(
        user_id=user.id,
        enabled=not setting.enabled,
        offsets_minutes=setting.offsets_minutes,
    )
    logger.info("bot.reminders.toggle", user_id=user.id, new_enabled=not setting.enabled)
    refreshed = await service.get(user.id)
    assert refreshed is not None
    await _render_menu_edit(query, refreshed)


@router.callback_query(AddOffsetCb.filter())
@require_active_user
async def on_add_offset(query: CallbackQuery, user: User | None, session: AsyncSession) -> None:
    assert user is not None
    if isinstance(query.message, Message):
        await query.message.edit_text(
            texts.REMINDERS_ADD_PROMPT,
            reply_markup=keyboards.reminders_add_kbd(),
        )
    await query.answer()


@router.callback_query(PresetOffsetCb.filter())
@require_active_user
async def on_preset_offset(
    query: CallbackQuery,
    callback_data: PresetOffsetCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    assert user is not None
    service = ReminderService(session)
    setting = await service.get(user.id)
    assert setting is not None
    new_offsets = [*setting.offsets_minutes, callback_data.minutes]
    try:
        await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
    except InvalidReminderOffsetsError as exc:
        await query.answer(_format_error(exc), show_alert=True)
        return
    logger.info("bot.reminders.preset_added", user_id=user.id, minutes=callback_data.minutes)
    refreshed = await service.get(user.id)
    assert refreshed is not None
    await _render_menu_edit(query, refreshed)


@router.callback_query(CustomOffsetCb.filter())
@require_active_user
async def on_custom_offset(
    query: CallbackQuery,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    assert user is not None
    await state.set_state(EditingReminders.adding_offset)
    if isinstance(query.message, Message):
        await query.message.edit_text(texts.REMINDERS_ASK_CUSTOM)
    await query.answer()


@router.message(EditingReminders.adding_offset, F.text)
@require_active_user
async def on_custom_offset_input(
    message: Message,
    user: User | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    assert user is not None
    assert message.text is not None
    minutes = parse_offset(message.text)
    if minutes is None:
        await message.answer(texts.REMINDERS_INVALID_INPUT)
        # state НЕ сбрасываем — даём попробовать ещё раз.
        return

    service = ReminderService(session)
    setting = await service.get(user.id)
    assert setting is not None
    new_offsets = [*setting.offsets_minutes, minutes]
    try:
        await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
    except InvalidReminderOffsetsError as exc:
        await message.answer(_format_error(exc))
        # state остаётся, пусть пользователь попробует другое значение.
        return

    await state.clear()
    refreshed = await service.get(user.id)
    assert refreshed is not None
    logger.info("bot.reminders.custom_added", user_id=user.id, minutes=minutes)
    await message.answer(
        texts.REMINDERS_ADDED.format(humanized=keyboards.humanize_minutes(minutes))
        + "\n\n"
        + _format_menu_text(refreshed),
        reply_markup=keyboards.reminders_menu_kbd(refreshed),
    )


@router.callback_query(RemoveOffsetCb.filter())
@require_active_user
async def on_remove_offset(
    query: CallbackQuery,
    callback_data: RemoveOffsetCb,
    user: User | None,
    session: AsyncSession,
) -> None:
    assert user is not None
    service = ReminderService(session)
    setting = await service.get(user.id)
    assert setting is not None
    new_offsets = [m for m in setting.offsets_minutes if m != callback_data.minutes]
    await service.update(user_id=user.id, enabled=setting.enabled, offsets_minutes=new_offsets)
    logger.info("bot.reminders.removed", user_id=user.id, minutes=callback_data.minutes)
    refreshed = await service.get(user.id)
    assert refreshed is not None
    await _render_menu_edit(query, refreshed)
