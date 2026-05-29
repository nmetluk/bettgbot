"""Integration-тесты `StatsService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import LeaderboardRow, StatsService
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_stats_empty_user(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = StatsService(nested_session)
    assert await service.user_stats(user.id) == (0, 0, 0.0)


async def test_stats_2_correct_of_5(nested_session: AsyncSession) -> None:
    user = await make_user(nested_session)
    service = StatsService(nested_session)

    # 5 событий с прогнозом, 2 — верных.
    for i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        pred = Prediction(
            user_id=user.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=(i < 2),
        )
        nested_session.add(pred)
    await nested_session.flush()

    correct, total, percent = await service.user_stats(user.id)
    assert correct == 2
    assert total == 5
    assert percent == 40.0


async def test_leaderboard_returns_ranked_rows(nested_session: AsyncSession) -> None:
    """Рейтинг возвращает типизированные строки с правильным рангом."""
    service = StatsService(nested_session)

    # Создаём пользователей с разной точностью
    u1 = await make_user(nested_session, first_name="First", last_name="Place")
    u2 = await make_user(nested_session, first_name="Second", last_name="Place")
    u3 = await make_user(nested_session, first_name="Third", last_name="Place")

    # u1: 5/5 = 100%
    for _i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        nested_session.add(
            Prediction(
                user_id=u1.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=True,
            )
        )

    # u2: 3/5 = 60%
    for i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        nested_session.add(
            Prediction(
                user_id=u2.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=i < 3,
            )
        )

    # u3: 4/6 = 66.7%
    for i in range(6):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        nested_session.add(
            Prediction(
                user_id=u3.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=i < 4,
            )
        )

    await nested_session.flush()

    rows = await service.leaderboard(min_resolved=5, limit=100)

    assert len(rows) == 2  # u3 ниже порога (только 4/6, но resolved=6 >=5)
    # Ой, у u3 resolved=6 >=5, значит он в рейтинге
    # u1: 5/5, u2: 3/5, u3: 4/6
    assert len(rows) == 3

    # Проверяем тип и поля первой строки (u1, 100%)
    assert isinstance(rows[0], LeaderboardRow)
    assert rows[0].rank == 1
    assert rows[0].user_id == u1.id
    assert rows[0].display_name == "First Place"
    assert rows[0].correct == 5
    assert rows[0].resolved == 5
    assert rows[0].accuracy == 100.0

    # Вторая строка (u3, 66.7%)
    assert rows[1].rank == 2
    assert rows[1].user_id == u3.id
    assert rows[1].accuracy < 67 and rows[1].accuracy > 66

    # Третья строка (u2, 60%)
    assert rows[2].rank == 3
    assert rows[2].user_id == u2.id
    assert rows[2].accuracy == 60.0


async def test_leaderboard_period_filter(nested_session: AsyncSession) -> None:
    """Параметр period_days фильтрует по created_at."""
    from datetime import UTC, datetime, timedelta

    service = StatsService(nested_session)
    u = await make_user(nested_session, first_name="Period")

    # Старые прогнозы (100 дней назад)
    old_date = datetime.now(tz=UTC) - timedelta(days=100)
    for _i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        pred = Prediction(
            user_id=u.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=True,
            created_at=old_date,
        )
        nested_session.add(pred)

    # Новые прогнозы (сегодня)
    for _i in range(5):
        event = await make_event(nested_session)
        outcome = await make_outcome(nested_session, event.id)
        pred = Prediction(
            user_id=u.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=False,
        )
        nested_session.add(pred)

    await nested_session.flush()

    # All-time — все 10
    all_rows = await service.leaderboard(min_resolved=5, limit=100, period_days=None)
    assert len(all_rows) == 1
    assert all_rows[0].resolved == 10

    # 30 дней — только 5 новых
    recent_rows = await service.leaderboard(min_resolved=5, limit=100, period_days=30)
    assert len(recent_rows) == 1
    assert recent_rows[0].resolved == 5
