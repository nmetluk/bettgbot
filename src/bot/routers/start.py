"""Handler `/start` и приём контакта при регистрации (TASK-011).

Сценарий:
- `/start` — приветствие (новый → просим контакт; существующий → главное меню;
  заблокированный → отказ без клавиатуры).
- `Message(F.contact)` — приём контакта, проверка во внешнем реестре через
  `UserService.register_or_authenticate`, обработка доменных исключений.
"""

from __future__ import annotations

import hashlib

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.exceptions import RegistryUnavailableError, UserNotAllowed
from src.shared.external.registry import ExternalUserRegistryClient
from src.shared.logging import get_logger
from src.shared.models import User
from src.shared.services import UserService

from .. import keyboards, texts

__all__ = ["router"]


logger = get_logger(__name__)

router = Router(name="start")


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:8]


def _normalize_phone(raw: str) -> str:
    """Telegram отдаёт `phone_number` без `+`; приводим к E.164."""
    return raw if raw.startswith("+") else f"+{raw}"


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user: User | None,
    state: FSMContext,
) -> None:
    # Сбрасываем FSM на случай, если пользователь /start'ит в середине FSM-flow
    # (например, выбора события в TASK-013).
    await state.clear()

    if user is not None and user.is_blocked:
        await message.answer(
            texts.ACCESS_DENIED,
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if user is None:
        await message.answer(
            texts.WELCOME_NEW,
            reply_markup=keyboards.contact_request(),
        )
        return

    logger.info("bot.start.returning_user", user_id=user.id)
    await message.answer(
        texts.WELCOME_RETURNING,
        reply_markup=keyboards.main_menu(),
    )


@router.message(F.contact)
async def on_contact(
    message: Message,
    session: AsyncSession,
    registry: ExternalUserRegistryClient,
    user: User | None,
) -> None:
    # Narrowing: F.contact гарантирует contact, CommandStart-like context — from_user.
    if message.contact is None or message.from_user is None:
        return

    if user is not None and user.is_blocked:
        await message.answer(texts.ACCESS_DENIED, reply_markup=ReplyKeyboardRemove())
        return

    # Telegram позволяет поделиться чужим контактом — мы принимаем только свой.
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            texts.NEED_OWN_CONTACT,
            reply_markup=keyboards.contact_request(),
        )
        return

    if user is not None:
        await message.answer(
            texts.ALREADY_REGISTERED,
            reply_markup=keyboards.main_menu(),
        )
        return

    phone = _normalize_phone(message.contact.phone_number)
    service = UserService(session, registry=registry)

    try:
        created = await service.register_or_authenticate(
            tg_user_id=message.from_user.id,
            phone=phone,
            tg_username=message.from_user.username,
            first_name=message.contact.first_name,
            last_name=message.contact.last_name,
        )
    except UserNotAllowed as exc:
        logger.info(
            "bot.start.not_allowed",
            tg_user_id=message.from_user.id,
            phone_hash=_phone_hash(phone),
            reason=exc.reason,
        )
        await message.answer(
            texts.PHONE_NOT_FOUND,
            reply_markup=keyboards.contact_request(),
        )
        return
    except RegistryUnavailableError:
        logger.warning(
            "bot.start.registry_unavailable",
            tg_user_id=message.from_user.id,
            phone_hash=_phone_hash(phone),
        )
        await message.answer(
            texts.REGISTRY_UNAVAILABLE,
            reply_markup=keyboards.contact_request(),
        )
        return

    logger.info(
        "bot.start.registered",
        tg_user_id=message.from_user.id,
        phone_hash=_phone_hash(phone),
        user_id=created.id,
    )
    await message.answer(
        texts.WELCOME_NEW_REGISTERED.format(first_name=created.first_name),
        reply_markup=keyboards.main_menu(),
    )
