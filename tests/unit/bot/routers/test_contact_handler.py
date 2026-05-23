"""Тесты `on_contact` — ветки регистрации и доменные исключения."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from src.bot import texts
from src.bot.routers.start import on_contact
from src.shared.exceptions import RegistryUnavailableError, UserNotAllowed


def _mock_message(*, contact_user_id: int = 12345) -> MagicMock:
    message = MagicMock()
    message.answer = AsyncMock()
    message.from_user = MagicMock(id=12345, username="alice")
    message.contact = MagicMock(
        user_id=contact_user_id,
        phone_number="71234567890",
        first_name="Alice",
        last_name=None,
    )
    return message


def _patch_user_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    register: Any = None,
    raises: Exception | None = None,
) -> AsyncMock:
    if raises is not None:
        register_mock = AsyncMock(side_effect=raises)
    else:
        register_mock = AsyncMock(return_value=register or MagicMock(id=99, first_name="Alice"))
    service_instance = MagicMock()
    service_instance.register_or_authenticate = register_mock
    monkeypatch.setattr(
        "src.bot.routers.start.UserService",
        MagicMock(return_value=service_instance),
    )
    return register_mock


async def test_contact_other_user_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    register = _patch_user_service(monkeypatch)
    message = _mock_message(contact_user_id=999)
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=None)

    register.assert_not_awaited()
    args, kwargs = message.answer.call_args
    assert args[0] == texts.NEED_OWN_CONTACT
    assert isinstance(kwargs["reply_markup"], ReplyKeyboardMarkup)


async def test_contact_blocked_user_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    register = _patch_user_service(monkeypatch)
    message = _mock_message()
    user = MagicMock(is_blocked=True)
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=user)

    register.assert_not_awaited()
    args, kwargs = message.answer.call_args
    assert args[0] == texts.ACCESS_DENIED
    assert isinstance(kwargs["reply_markup"], ReplyKeyboardRemove)


async def test_contact_already_registered_shows_main_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register = _patch_user_service(monkeypatch)
    message = _mock_message()
    user = MagicMock(is_blocked=False)
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=user)

    register.assert_not_awaited()
    args, _kwargs = message.answer.call_args
    assert args[0] == texts.ALREADY_REGISTERED


async def test_contact_happy_path_registers_user_and_shows_main_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = MagicMock(id=42, first_name="Alice")
    register = _patch_user_service(monkeypatch, register=created)
    message = _mock_message()
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=None)

    register.assert_awaited_once()
    kwargs = register.call_args.kwargs
    # phone приведён к E.164 (с `+`).
    assert kwargs["phone"] == "+71234567890"
    assert kwargs["tg_user_id"] == 12345
    assert kwargs["first_name"] == "Alice"

    args, kwargs_resp = message.answer.call_args
    assert args[0] == texts.WELCOME_NEW_REGISTERED.format(first_name="Alice")
    assert isinstance(kwargs_resp["reply_markup"], ReplyKeyboardMarkup)


async def test_contact_user_not_allowed_sends_phone_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_user_service(monkeypatch, raises=UserNotAllowed(reason="not_found"))
    message = _mock_message()
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=None)

    args, kwargs = message.answer.call_args
    assert args[0] == texts.PHONE_NOT_FOUND
    assert isinstance(kwargs["reply_markup"], ReplyKeyboardMarkup)


async def test_contact_registry_unavailable_sends_retry_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_user_service(monkeypatch, raises=RegistryUnavailableError("down"))
    message = _mock_message()
    await on_contact(message, session=MagicMock(), registry=MagicMock(), user=None)

    args, kwargs = message.answer.call_args
    assert args[0] == texts.REGISTRY_UNAVAILABLE
    assert isinstance(kwargs["reply_markup"], ReplyKeyboardMarkup)
