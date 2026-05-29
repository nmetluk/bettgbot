"""Integration-тесты `dispatch_broadcasts` job (TASK-061-amendment)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.scheduler.jobs import dispatch_broadcasts
from src.shared.models import Broadcast
from src.shared.repositories import BroadcastRepository
from tests.integration.conftest import make_admin, make_user

pytestmark = pytest.mark.integration


async def test_dispatch_broadcasts_sends_to_recipients(clean_session: AsyncSession) -> None:
    """dispatch_broadcasts отправляет сообщение всем получателям сегмента."""
    admin = await make_admin(clean_session)
    user1 = await make_user(clean_session, is_blocked=False)
    user2 = await make_user(clean_session, is_blocked=False)
    blocked = await make_user(clean_session, is_blocked=True)  # Не должен получить

    repo = BroadcastRepository(clean_session)

    # Создаём рассылку
    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test broadcast",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await repo.update_total_recipients(broadcast.id, 2)  # Двое неблокированных
    await clean_session.commit()

    # Мокаем Bot
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    # Запускаем job
    await dispatch_broadcasts(bot=bot, session_maker=lambda: clean_session)

    # Проверяем, что send_message был вызван 2 раза (user1 и user2)
    assert bot.send_message.call_count == 2

    # Проверяем, что заблокированный пользователь не получил сообщение
    called_ids = {call[0][0] for call in bot.send_message.call_args_list}
    assert user1.tg_user_id in called_ids
    assert user2.tg_user_id in called_ids
    assert blocked.tg_user_id not in called_ids

    # Проверяем статус рассылки
    updated = await repo.get_by_id(broadcast.id)
    assert updated is not None
    assert updated.status == "done"
    assert updated.sent_count == 2
    assert updated.failed_count == 0


async def test_dispatch_broadcasts_handles_send_errors(clean_session: AsyncSession) -> None:
    """dispatch_broadcasts продолжает работу при ошибках отправки."""
    from aiogram.exceptions import TelegramAPIError

    admin = await make_admin(clean_session)
    user1 = await make_user(clean_session, is_blocked=False)
    user2 = await make_user(clean_session, is_blocked=False)

    repo = BroadcastRepository(clean_session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test broadcast",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await repo.update_total_recipients(broadcast.id, 2)
    await clean_session.commit()

    # Мокаем Bot: первая попытка падает, вторая успешна
    bot = AsyncMock()
    error = TelegramAPIError(method="send_message", message="Blocked by user")
    bot.send_message = AsyncMock(side_effect=[error, MagicMock()])

    await dispatch_broadcasts(bot=bot, session_maker=lambda: clean_session)

    updated = await repo.get_by_id(broadcast.id)
    assert updated.status == "done"
    assert updated.sent_count == 1
    assert updated.failed_count == 1


async def test_dispatch_broadcasts_is_idempotent(clean_session: AsyncSession) -> None:
    """Повторный вызов не отправляет сообщения уже доставшим пользователям."""
    from src.shared.models import BroadcastDelivery

    admin = await make_admin(clean_session)
    user1 = await make_user(clean_session, is_blocked=False)

    repo = BroadcastRepository(clean_session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test broadcast",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await repo.update_total_recipients(broadcast.id, 1)
    await clean_session.commit()

    # Вручную записываем доставку (имитируем предыдущий запуск)
    recorded = await repo.record_delivery(broadcast.id, user1.id)
    assert recorded is True
    await clean_session.commit()

    # Запускаем с рабочим bot
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    await dispatch_broadcasts(bot=bot, session_maker=lambda: clean_session)

    # Сообщение не должно быть отправлено (уже доставлено)
    assert bot.send_message.call_count == 0

    # Проверяем, что рассылка завершилась успешно
    updated = await repo.get_by_id(broadcast.id)
    assert updated.status == "done"


async def test_dispatch_broadcasts_skips_empty_segment(clean_session: AsyncSession) -> None:
    """dispatch_broadcasts завершает рассылку если сегмент пуст."""
    admin = await make_admin(clean_session)

    repo = BroadcastRepository(clean_session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test broadcast",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await repo.update_total_recipients(broadcast.id, 0)  # Пустой сегмент
    await clean_session.commit()

    bot = AsyncMock()
    await dispatch_broadcasts(bot=bot, session_maker=lambda: clean_session)

    updated = await repo.get_by_id(broadcast.id)
    assert updated.status == "done"
    assert bot.send_message.call_count == 0


async def test_dispatch_broadcasts_commits_in_batches(clean_session: AsyncSession) -> None:
    """dispatch_broadcasts коммитит порциями для идемпотентности."""
    admin = await make_admin(clean_session)

    # Создаём 5 пользователей
    users = [await make_user(clean_session, is_blocked=False) for _ in range(5)]

    repo = BroadcastRepository(clean_session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test broadcast",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await repo.update_total_recipients(broadcast.id, 5)
    await clean_session.commit()

    bot = AsyncMock()
    bot.send_message = AsyncMock()

    # Запускаем с маленьким batch_size для теста
    await dispatch_broadcasts(bot=bot, session_maker=lambda: clean_session, commit_batch_size=2)

    # Все сообщения отправлены
    assert bot.send_message.call_count == 5

    updated = await repo.get_by_id(broadcast.id)
    assert updated.status == "done"
    assert updated.sent_count == 5
