"""Integration-тесты `BroadcastRepository` (TASK-061-amendment)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import User
from src.shared.repositories import BroadcastRepository
from tests.integration.conftest import make_admin, make_category, make_event, make_user

pytestmark = pytest.mark.integration


async def test_recipients_for_all_returns_unblocked_users(session: AsyncSession) -> None:
    """Сегмент `all` возвращает всех неблокированных пользователей."""
    blocked = await make_user(session, is_blocked=True)
    active = await make_user(session, is_blocked=False)
    inactive = await make_user(session, is_blocked=False)

    repo = BroadcastRepository(session)
    recipients = await repo.recipients_for("all")

    assert active.id in recipients
    assert inactive.id in recipients
    assert blocked.id not in recipients
    # Два новых неблокированных + существующие
    assert len(recipients) >= 2


async def test_recipients_for_active_filters_by_last_seen(session: AsyncSession) -> None:
    """Сегмент `active` возвращает только пользователей с last_seen_at >= 30 дней."""
    # Активный: заходил 25 дней назад
    active = await make_user(session, is_blocked=False, last_seen_at=datetime.now(tz=UTC) - timedelta(days=25))
    # Неактивный: заходил 35 дней назад
    inactive = await make_user(session, is_blocked=False, last_seen_at=datetime.now(tz=UTC) - timedelta(days=35))
    # Заблокированный даже если активный
    blocked = await make_user(session, is_blocked=True, last_seen_at=datetime.now(tz=UTC) - timedelta(days=25))

    repo = BroadcastRepository(session)
    recipients = await repo.recipients_for("active")

    assert active.id in recipients
    assert inactive.id not in recipients
    assert blocked.id not in recipients


async def test_recipients_for_category_returns_users_with_predictions(session: AsyncSession) -> None:
    """Сегмент `category` возвращает пользователей с прогнозами в категории."""
    category = await make_category(session)
    other_category = await make_category(session)

    event_in_cat = await make_event(session, category=category)
    event_other_cat = await make_event(session, category=other_category)

    # Создаём пользователей
    user1 = await make_user(session, is_blocked=False)
    user2 = await make_user(session, is_blocked=False)
    user3 = await make_user(session, is_blocked=False)
    blocked = await make_user(session, is_blocked=True)

    # Создаём outcomes для прогнозов
    from tests.integration.conftest import make_outcome

    outcome1 = await make_outcome(session, event_in_cat.id, label="A")
    outcome2 = await make_outcome(session, event_other_cat.id, label="B")

    # User1 делал прогноз в категории
    session.add(
        await _make_prediction(session, user_id=user1.id, event_id=event_in_cat.id, outcome_id=outcome1.id)
    )
    # User2 делал прогноз в другой категории
    session.add(
        await _make_prediction(session, user_id=user2.id, event_id=event_other_cat.id, outcome_id=outcome2.id)
    )
    # User3 делал прогноз в обеих
    session.add(
        await _make_prediction(session, user_id=user3.id, event_id=event_in_cat.id, outcome_id=outcome1.id)
    )
    session.add(
        await _make_prediction(session, user_id=user3.id, event_id=event_other_cat.id, outcome_id=outcome2.id)
    )
    # Blocked делал прогноз в категории
    session.add(
        await _make_prediction(session, user_id=blocked.id, event_id=event_in_cat.id, outcome_id=outcome1.id)
    )

    await session.flush()

    repo = BroadcastRepository(session)
    recipients = await repo.recipients_for("category", category_id=category.id)

    assert user1.id in recipients
    assert user3.id in recipients
    assert user2.id not in recipients  # Другая категория
    assert blocked.id not in recipients  # Заблокирован


async def test_claim_next_queued_transitions_to_sending(session: AsyncSession) -> None:
    """claim_next_queued атомарно забирает queued-рассылку и переводит в sending."""
    from src.shared.models import Broadcast

    # Очищаем таблицу broadcast от предыдущих тестов
    existing = await session.execute(select(Broadcast))
    for b in existing.scalars().all():
        await session.delete(b)
    await session.flush()

    admin = await make_admin(session)
    repo = BroadcastRepository(session)

    # Создаём две рассылки
    broadcast1 = await repo.create_draft(
        segment="all",
        message_text="Test 1",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast1.id)

    broadcast2 = await repo.create_draft(
        segment="all",
        message_text="Test 2",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast2.id)

    await session.flush()

    # Первый claim забирает первую
    claimed = await repo.claim_next_queued()
    assert claimed is not None
    assert claimed.id == broadcast1.id
    assert claimed.status == "sending"
    assert claimed.started_at is not None

    await session.commit()

    # Повторный call не возвращает ту же (уже sending)
    second_claim = await repo.claim_next_queued()
    assert second_claim is not None
    assert second_claim.id == broadcast2.id
    assert second_claim.status == "sending"


async def test_claim_next_queued_returns_none_when_empty(session: AsyncSession) -> None:
    """claim_next_queued возвращает None когда нет queued-рассылок."""
    from src.shared.models import Broadcast

    # Очищаем таблицу broadcast от предыдущих тестов
    await session.execute(select(Broadcast).where(Broadcast.id > 0))
    existing = await session.execute(select(Broadcast))
    if existing.scalars().first():
        # Удаляем существующие записи
        for b in (await session.execute(select(Broadcast))).scalars().all():
            await session.delete(b)
        await session.flush()

    repo = BroadcastRepository(session)
    claimed = await repo.claim_next_queued()
    assert claimed is None


async def test_record_delivery_is_idempotent(session: AsyncSession) -> None:
    """record_delivery возвращает False при повторном вызове (UNIQUE constraint)."""
    admin = await make_admin(session)
    user = await make_user(session)
    repo = BroadcastRepository(session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test",
        created_by_admin_id=admin.id,
    )
    await session.flush()

    # Первая запись успешна
    first = await repo.record_delivery(broadcast.id, user.id)
    assert first is True

    await session.flush()

    # Повторная запись не создаёт дубликат
    second = await repo.record_delivery(broadcast.id, user.id)
    assert second is False

    await session.commit()

    # Проверяем, что только одна запись в БД
    from src.shared.models import BroadcastDelivery

    result = await session.execute(
        select(BroadcastDelivery).where(
            BroadcastDelivery.broadcast_id == broadcast.id,
            BroadcastDelivery.user_id == user.id,
        )
    )
    deliveries = result.scalars().all()
    assert len(deliveries) == 1


async def test_count_recipients_for_all(session: AsyncSession) -> None:
    """count_recipients_for возвращает точное число для сегмента all."""
    # Получаем existing count
    existing_result = await session.execute(
        select(func.count(User.id)).where(User.is_blocked.is_(False))
    )
    existing_count = existing_result.scalar_one() or 0

    user1 = await make_user(session, is_blocked=False)
    await make_user(session, is_blocked=False)  # второй пользователь
    blocked = await make_user(session, is_blocked=True)  # Не считается

    # Проверяем, что is_blocked применился
    assert blocked.is_blocked is True, f"blocked.is_blocked={blocked.is_blocked}"
    assert user1.is_blocked is False

    repo = BroadcastRepository(session)
    count = await repo.count_recipients_for("all")
    # Два новых неблокированных + существующие
    assert count == existing_count + 2


async def test_count_recipients_for_active(session: AsyncSession) -> None:
    """count_recipients_for возвращает точное число для сегмента active."""
    # Получаем existing count для active
    cutoff = datetime.now(tz=UTC) - timedelta(days=30)
    existing_result = await session.execute(
        select(func.count(User.id)).where(
            User.is_blocked.is_(False),
            User.last_seen_at >= cutoff,
        )
    )
    existing_count = existing_result.scalar_one() or 0

    await make_user(
        session, is_blocked=False, last_seen_at=datetime.now(tz=UTC) - timedelta(days=25)
    )
    await make_user(
        session, is_blocked=False, last_seen_at=datetime.now(tz=UTC) - timedelta(days=35)
    )

    repo = BroadcastRepository(session)
    count = await repo.count_recipients_for("active")
    # Один новый активный + существующие
    assert count == existing_count + 1


async def test_mark_done_updates_status_and_timestamps(session: AsyncSession) -> None:
    """mark_done обновляет статус на done и устанавливает finished_at."""
    admin = await make_admin(session)
    repo = BroadcastRepository(session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test",
        created_by_admin_id=admin.id,
    )
    await repo.enqueue(broadcast.id)
    await session.flush()

    # Эмулируем claim (ручной перевод в sending)
    broadcast.status = "sending"
    broadcast.started_at = datetime.now(tz=UTC)
    await session.flush()

    await repo.mark_done(broadcast.id)
    await session.commit()

    await session.refresh(broadcast)
    assert broadcast.status == "done"
    assert broadcast.finished_at is not None


async def test_increment_sent_and_failed(session: AsyncSession) -> None:
    """increment_sent и increment_failed корректно обновляют счётчики."""
    admin = await make_admin(session)
    repo = BroadcastRepository(session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test",
        created_by_admin_id=admin.id,
    )
    await session.flush()

    await repo.increment_sent(broadcast.id)
    await repo.increment_sent(broadcast.id)
    await repo.increment_failed(broadcast.id)
    await session.commit()

    await session.refresh(broadcast)
    assert broadcast.sent_count == 2
    assert broadcast.failed_count == 1


async def test_update_total_recipients(session: AsyncSession) -> None:
    """update_total_recipients обновляет total_recipients."""
    admin = await make_admin(session)
    repo = BroadcastRepository(session)

    broadcast = await repo.create_draft(
        segment="all",
        message_text="Test",
        created_by_admin_id=admin.id,
    )
    await session.flush()

    await repo.update_total_recipients(broadcast.id, 42)
    await session.commit()

    await session.refresh(broadcast)
    assert broadcast.total_recipients == 42


# Helper для создания прогноза
async def _make_prediction(session: AsyncSession, user_id: int, event_id: int, outcome_id: int) -> Any:
    from src.shared.models import Prediction

    pred = Prediction(
        user_id=user_id,
        event_id=event_id,
        outcome_id=outcome_id,
    )
    session.add(pred)
    await session.flush()
    return pred
