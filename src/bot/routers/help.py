"""Router `/help` — статическая справка (TASK-016)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import User

from .. import keyboards, texts
from ..auth import require_active_user

__all__ = ["router"]


router = Router(name="help")


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Справка")
@require_active_user
async def cmd_help(
    message: Message,
    user: User | None,
    session: AsyncSession,
) -> None:
    """Отвечает статическим текстом справки + клавиатура главного меню."""
    await message.answer(texts.HELP, reply_markup=keyboards.main_menu())
