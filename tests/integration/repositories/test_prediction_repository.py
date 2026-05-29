"""Integration-тесты `PredictionRepository`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.repositories import PredictionRepository
from tests.integration.conftest import make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


async def test_upsert_inserts_then_updates(session: AsyncSession) -> None:
    event = await make_event(session)
    o1 = await make_outcome(session, event.id, label="A")
    o2 = await make_outcome(session, event.id, label="B")
    user = await make_user(session)
    repo = PredictionRepository(session)

    inserted = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o1.id)
    assert inserted.outcome_id == o1.id

    updated = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o2.id)
    assert updated.id == inserted.id
    assert updated.outcome_id == o2.id


async def test_mark_correctness_sets_true_false(session: AsyncSession) -> None:
    event = await make_event(session)
    correct = await make_outcome(session, event.id, label="correct")
    wrong = await make_outcome(session, event.id, label="wrong")

    u1 = await make_user(session)
    u2 = await make_user(session)
    repo = PredictionRepository(session)
    await repo.upsert(user_id=u1.id, event_id=event.id, outcome_id=correct.id)
    await repo.upsert(user_id=u2.id, event_id=event.id, outcome_id=wrong.id)

    rowcount = await repo.mark_correctness(event.id, correct.id)
    assert rowcount == 2

    p1 = await repo.get_by_user_event(u1.id, event.id)
    p2 = await repo.get_by_user_event(u2.id, event.id)
    assert p1 is not None and p1.is_correct is True
    assert p2 is not None and p2.is_correct is False


async def test_user_stats(session: AsyncSession) -> None:
    event = await make_event(session)
    o = await make_outcome(session, event.id, label="X")
    user = await make_user(session)
    repo = PredictionRepository(session)
    pred = await repo.upsert(user_id=user.id, event_id=event.id, outcome_id=o.id)

    correct, total = await repo.user_stats(user.id)
    assert correct == 0 and total == 0

    pred.is_correct = True
    await session.flush()
    correct, total = await repo.user_stats(user.id)
    assert correct == 1 and total == 1


async def test_list_active_and_archived(session: AsyncSession) -> None:
    user = await make_user(session)
    active_event = await make_event(session, is_archived=False)
    o1 = await make_outcome(session, active_event.id)
    repo = PredictionRepository(session)
    await repo.upsert(user_id=user.id, event_id=active_event.id, outcome_id=o1.id)

    active = await repo.list_active_by_user(user.id)
    assert any(p.event_id == active_event.id for p in active)
    archived = await repo.list_archived_by_user(user.id)
    assert all(p.event_id != active_event.id for p in archived)


async def test_users_without_prediction_for_event(session: AsyncSession) -> None:
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    u_with = await make_user(session)
    u_without = await make_user(session)
    u_blocked = await make_user(session, is_blocked=True)

    repo = PredictionRepository(session)
    await repo.upsert(user_id=u_with.id, event_id=event.id, outcome_id=outcome.id)

    ids = await repo.users_without_prediction_for_event(event.id)
    assert u_without.id in ids
    assert u_with.id not in ids
    assert u_blocked.id not in ids


async def test_count_returns_total_predictions(session: AsyncSession) -> None:
    """Счётчик возвращает общее количество прогнозов."""
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    u1 = await make_user(session)
    u2 = await make_user(session)

    repo = PredictionRepository(session)
    await repo.upsert(user_id=u1.id, event_id=event.id, outcome_id=outcome.id)
    await repo.upsert(user_id=u2.id, event_id=event.id, outcome_id=outcome.id)

    assert await repo.count() == 2


async def test_leaderboard_threshold_and_sorting(session: AsyncSession) -> None:
    """Рейтинг отсекает ниже порога min_resolved и сортирует по точности."""
    repo = PredictionRepository(session)

    # Пользователь A: 5/5 = 100%
    u_a = await make_user(session, first_name="Alice")
    # Пользователь B: 3/5 = 60%
    u_b = await make_user(session, first_name="Bob")
    # Пользователь C: 4/6 = 66.7%
    u_c = await make_user(session, first_name="Charlie")
    # Пользователь D: 2/4 = 50% (ниже порога 5)
    u_d = await make_user(session, first_name="Dave")
    # Заблокированный: 5/5 = 100% (должен быть исключён)
    u_blocked = await make_user(session, first_name="Blocked", is_blocked=True)

    for i in range(5):
        event = await make_event(session)
        outcome = await make_outcome(session, event.id)
        # u_a — все верные
        pred_a = Prediction(
            user_id=u_a.id, event_id=event.id, outcome_id=outcome.id, is_correct=True
        )
        session.add(pred_a)
        # u_b — 3 из 5 верных
        is_correct_b = i < 3
        pred_b = Prediction(
            user_id=u_b.id, event_id=event.id, outcome_id=outcome.id, is_correct=is_correct_b
        )
        session.add(pred_b)
        # u_blocked — все верные
        pred_blocked = Prediction(
            user_id=u_blocked.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=True,
        )
        session.add(pred_blocked)

    # u_c — 6 прогнозов, 4 верных
    for i in range(6):
        event = await make_event(session)
        outcome = await make_outcome(session, event.id)
        pred_c = Prediction(
            user_id=u_c.id, event_id=event.id, outcome_id=outcome.id, is_correct=i < 4
        )
        session.add(pred_c)

    # u_d — 4 прогноза, 2 верных (ниже порога 5)
    for i in range(4):
        event = await make_event(session)
        outcome = await make_outcome(session, event.id)
        pred_d = Prediction(
            user_id=u_d.id, event_id=event.id, outcome_id=outcome.id, is_correct=i < 2
        )
        session.add(pred_d)

    await session.flush()

    rows = await repo.leaderboard(min_resolved=5, limit=100)

    # Должны быть только A, B, C (D — ниже порога, blocked — исключён)
    assert len(rows) == 3

    # Сортировка: A (100%), C (66.7%), B (60%)
    assert rows[0][0] == u_a.id  # user_id
    assert rows[0][1] == 5  # correct
    assert rows[0][2] == 5  # resolved
    assert rows[0][4] == 100.0  # accuracy

    assert rows[1][0] == u_c.id
    assert rows[1][1] == 4
    assert rows[1][2] == 6
    assert abs(rows[1][4] - 66.7) < 0.1

    assert rows[2][0] == u_b.id
    assert rows[2][1] == 3
    assert rows[2][2] == 5
    assert rows[2][4] == 60.0


async def test_leaderboard_tiebreak_by_correct_then_resolved(
    session: AsyncSession,
) -> None:
    """При равной точности tiebreak: больше верных, затем больше разрешённых."""
    repo = PredictionRepository(session)

    # u1: 5/10 = 50%
    u1 = await make_user(session, first_name="One")
    # u2: 5/10 = 50% (равно с u1)
    u2 = await make_user(session, first_name="Two")
    # u3: 10/20 = 50% (равная точность, больше верных)
    u3 = await make_user(session, first_name="Three")

    for i in range(10):
        event = await make_event(session)
        outcome = await make_outcome(session, event.id)
        session.add(
            Prediction(
                user_id=u1.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=i < 5,
            )
        )
        session.add(
            Prediction(
                user_id=u2.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=i < 5,
            )
        )

    for i in range(20):
        event = await make_event(session)
        outcome = await make_outcome(session, event.id)
        session.add(
            Prediction(
                user_id=u3.id,
                event_id=event.id,
                outcome_id=outcome.id,
                is_correct=i < 10,
            )
        )

    await session.flush()

    rows = await repo.leaderboard(min_resolved=5, limit=100)

    # Все с точностью 50%, но u3 выше (больше верных)
    assert rows[0][0] == u3.id
    assert rows[0][1] == 10
    assert rows[0][4] == 50.0

    # u1 и u2 — порядок не гарантирован при полном равенстве
    user_ids = {rows[1][0], rows[2][0]}
    assert user_ids == {u1.id, u2.id}


async def test_leaderboard_empty(session: AsyncSession) -> None:
    """Пустой рейтинг, когда никто не прошёл порог."""
    repo = PredictionRepository(session)
    u = await make_user(session)
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)

    session.add(Prediction(user_id=u.id, event_id=event.id, outcome_id=outcome.id, is_correct=True))
    await session.flush()

    rows = await repo.leaderboard(min_resolved=5, limit=100)
    assert len(rows) == 0


async def test_leaderboard_respects_limit(session: AsyncSession) -> None:
    """Параметр limit ограничивает количество результатов."""
    repo = PredictionRepository(session)

    for i in range(10):
        user = await make_user(session, first_name=f"User{i}")
        for _j in range(5):
            event = await make_event(session)
            outcome = await make_outcome(session, event.id)
            session.add(
                Prediction(
                    user_id=user.id,
                    event_id=event.id,
                    outcome_id=outcome.id,
                    is_correct=True,
                )
            )

    await session.flush()

    rows = await repo.leaderboard(min_resolved=5, limit=3)
    assert len(rows) == 3
