"""Integration-тесты `StatsService`."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.services import (
    CorrectUserRow,
    EventResultSummary,
    LeaderboardRow,
    StatsService,
)
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

    # u1: 5/5, u2: 3/5, u3: 4/6 — все прошли порог (resolved >= 5)
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


# =============================================================================
# TASK-097: event_result_summary + 24h aggregates (per amendment + DoD)
# =============================================================================


async def test_event_result_summary_full(nested_session: AsyncSession) -> None:
    """Полная сводка по событию с несколькими исходами и смешанными прогнозами.

    Проверяет:
    - total_predictions / correct_count
    - outcome_distribution (с флагом is_winner по result_outcome_id)
    - correct_users (все поля для CSV, включая PII phone)
    """
    from src.shared.models import Prediction

    service = StatsService(nested_session)

    # Подготовка: событие + 3 исхода
    event = await make_event(nested_session)
    o1 = await make_outcome(nested_session, event.id, label="П1")
    o2 = await make_outcome(nested_session, event.id, label="Ничья")
    o3 = await make_outcome(nested_session, event.id, label="П2")

    # Делаем o1 победителем + архивируем (удовлетворяет ck_event_result_archive_consistency)
    from src.shared.time import utcnow

    event.is_archived = True
    event.archived_at = utcnow()
    event.result_outcome_id = o1.id
    await nested_session.flush()

    # 5 пользователей, 7 прогнозов
    users = []
    for i in range(5):
        u = await make_user(nested_session, first_name=f"U{i}", phone=f"+7999000000{i}")
        users.append(u)

    # Прогнозы (каждый пользователь — ровно один прогноз на событие):
    # U0, U1, U2 → o1 (П1, победитель) — верные: U0, U1 (2)
    # U3 → o2
    # U4 → o3
    preds = [
        (users[0], o1, True),
        (users[1], o1, True),
        (users[2], o1, False),
        (users[3], o2, False),
        (users[4], o3, False),
    ]
    for u, o, correct in preds:
        nested_session.add(
            Prediction(
                user_id=u.id,
                event_id=event.id,
                outcome_id=o.id,
                is_correct=correct,
            )
        )
    await nested_session.flush()

    summary = await service.event_result_summary(event.id)

    assert isinstance(summary, EventResultSummary)
    assert summary.total_predictions == 5
    assert summary.correct_count == 2  # U0, U1

    # Распределение: o1=3 (2 верных + 1 неверный), o2=1, o3=1
    dist = {(oid, label): (cnt, is_win) for oid, label, cnt, is_win in summary.outcome_distribution}
    assert dist[(o1.id, "П1")] == (3, True)  # winner
    assert dist[(o2.id, "Ничья")] == (1, False)
    assert dist[(o3.id, "П2")] == (1, False)

    # correct_users — 2 записи (с phone и остальными полями для CSV)
    assert len(summary.correct_users) == 2
    assert all(isinstance(r, CorrectUserRow) for r in summary.correct_users)
    phones = {r.phone for r in summary.correct_users}
    assert "+79990000000" in phones
    assert "+79990000001" in phones


async def test_digest_aggregates_24h_vs_old(nested_session: AsyncSession) -> None:
    """Проверка агрегатов дайджеста: новые за 24ч, прогнозы за 24ч, всего.

    Использует новые методы репозиториев, которые дёргает дайджест-джоб.

    Стабилизировано через delta-подход (baseline до создания тестовых данных),
    чтобы тест не зависел от мусора, оставленного предыдущими тестами в shared БД.
    """
    from datetime import UTC, datetime, timedelta

    from freezegun import freeze_time
    from src.shared.repositories import PredictionRepository, UserRepository

    with freeze_time("2026-06-01 12:00:00+00:00"):
        now = datetime.now(tz=UTC)
        cutoff_24h = now - timedelta(hours=24)
        # Используем сильно старые и сильно свежие метки, чтобы исключить
        # любые проблемы с границами окна и серверным временем БД
        very_old = now - timedelta(days=10)
        very_recent = now - timedelta(minutes=5)

        user_repo = UserRepository(nested_session)
        pred_repo = PredictionRepository(nested_session)

        # Baseline ДО создания тестовых данных (защита от pollution shared test DB)
        base_new = await user_repo.count_new_since(cutoff_24h)
        base_preds = await pred_repo.count_24h()

        # Старый пользователь + старый прогноз (гарантированно вне 24h окна)
        old_user = await make_user(nested_session, created_at=very_old)
        old_event = await make_event(nested_session)
        old_o = await make_outcome(nested_session, old_event.id)
        nested_session.add(
            Prediction(
                user_id=old_user.id, event_id=old_event.id, outcome_id=old_o.id, created_at=very_old
            )
        )

        # Новые пользователи + недавние прогнозы (ровно 2, внутри окна)
        new_u1 = await make_user(nested_session, created_at=very_recent, first_name="New1")
        new_u2 = await make_user(nested_session, created_at=very_recent, first_name="New2")
        new_event = await make_event(nested_session)
        new_o = await make_outcome(nested_session, new_event.id)
        nested_session.add(
            Prediction(
                user_id=new_u1.id,
                event_id=new_event.id,
                outcome_id=new_o.id,
                created_at=very_recent,
            )
        )
        nested_session.add(
            Prediction(
                user_id=new_u2.id,
                event_id=new_event.id,
                outcome_id=new_o.id,
                created_at=very_recent,
            )
        )

        await nested_session.flush()

        # Дельты должны быть ровно 2 (устойчиво к данным от других тестов)
        new_since = await user_repo.count_new_since(cutoff_24h)
        preds_24h = await pred_repo.count_24h()

        assert new_since - base_new == 2
        assert preds_24h - base_preds == 2


async def test_daily_admin_digest_full(nested_session: AsyncSession) -> None:
    """Полный тест обогащённого дайджеста: дельты, DAU, активные, топ, точность закрытых, конверсия."""
    from datetime import UTC, datetime, timedelta

    from src.shared.models import Prediction
    from src.shared.services import DailyAdminDigest, StatsService

    service = StatsService(nested_session)
    now = datetime.now(tz=UTC)
    very_old = now - timedelta(days=5)
    recent = now - timedelta(hours=1)
    prev_window = now - timedelta(hours=30)  # в 48-24

    # Базовые юзеры
    u_total = await make_user(nested_session)
    # Новые в текущем окне + с прогнозом (конверсия)
    u_new1 = await make_user(nested_session, created_at=recent)
    u_new2 = await make_user(nested_session, created_at=recent)
    # Старые
    u_old = await make_user(nested_session, created_at=very_old)
    # Для DAU: last_seen недавний (используем touch? но для простоты создадим с last_seen)
    # make_user не имеет last_seen override легко, используем прямой update после
    # Для теста, создадим и обновим last_seen через raw или просто используем created как proxy? Нет, для DAU last_seen.
    # Чтобы упростить, сделаем last_seen = recent для некоторых.
    # Поскольку модель, после flush обновим.
    # Для brevity: создадим 2 с last_seen недавним.

    # События
    e_active = await make_event(nested_session)
    o_a1 = await make_outcome(nested_session, e_active.id)
    o_a2 = await make_outcome(nested_session, e_active.id)
    # Сделаем active: published, not arch, close future
    e_active.is_published = True
    e_active.is_archived = False
    e_active.predictions_close_at = now + timedelta(hours=1)
    e_closed = await make_event(nested_session)
    o_win = await make_outcome(nested_session, e_closed.id, label="Win")
    e_closed.is_published = True
    e_closed.is_archived = True
    e_closed.archived_at = recent
    e_closed.result_outcome_id = o_win.id
    await nested_session.flush()

    # Прогнозы
    # В текущем 24h: 3 прогноза
    p1 = Prediction(user_id=u_new1.id, event_id=e_active.id, outcome_id=o_a1.id, created_at=recent)
    nested_session.add(p1)
    p2 = Prediction(user_id=u_new2.id, event_id=e_active.id, outcome_id=o_a2.id, created_at=recent)
    nested_session.add(p2)
    p3 = Prediction(user_id=u_total.id, event_id=e_closed.id, outcome_id=o_win.id, created_at=recent, is_correct=True)
    nested_session.add(p3)
    # В prev окне: 1 прогноз
    p_prev = Prediction(user_id=u_old.id, event_id=e_active.id, outcome_id=o_a1.id, created_at=prev_window)
    nested_session.add(p_prev)
    # Для closed: 1 correct выше

    # Новые без прогноза для конверсии: u_new1 has, u_new2 has? Подправим: один без
    # Для теста конверсии 1 из 2

    await nested_session.flush()

    # Обновим last_seen для DAU (2 юзера активны недавно)
    from sqlalchemy import update
    from src.shared.models import User

    await nested_session.execute(
        update(User).where(User.id.in_([u_new1.id, u_total.id])).values(last_seen_at=recent)
    )
    await nested_session.flush()

    d: DailyAdminDigest = await service.daily_admin_digest()

    assert d.total_users >= 4
    assert d.new_24h >= 2
    assert d.preds_24h >= 3
    assert d.dau_24h >= 2
    assert d.active_events_now >= 1
    assert len(d.top_events_24h) >= 1
    assert d.closed_total == 1 and d.closed_correct == 1
    assert d.conversion_pct is not None  # 1 converted out of some new


async def test_event_result_summary_enriched(nested_session: AsyncSession) -> None:
    """Проверка обогащения event_result_summary: majority_correct и participation."""
    from src.shared.models import Prediction
    from src.shared.services import StatsService
    from src.shared.time import utcnow

    service = StatsService(nested_session)

    event = await make_event(nested_session)
    o1 = await make_outcome(nested_session, event.id, label="П1")
    o2 = await make_outcome(nested_session, event.id, label="П2")
    event.is_published = True
    event.is_archived = True
    event.archived_at = utcnow()
    event.result_outcome_id = o1.id
    await nested_session.flush()

    # 3 прогноза на o2 (популярный, но не верный), 1 на o1
    u1 = await make_user(nested_session)
    u2 = await make_user(nested_session)
    u3 = await make_user(nested_session)
    u4 = await make_user(nested_session)
    nested_session.add(Prediction(user_id=u1.id, event_id=event.id, outcome_id=o2.id))
    nested_session.add(Prediction(user_id=u2.id, event_id=event.id, outcome_id=o2.id))
    nested_session.add(Prediction(user_id=u3.id, event_id=event.id, outcome_id=o2.id))
    nested_session.add(Prediction(user_id=u4.id, event_id=event.id, outcome_id=o1.id, is_correct=True))
    await nested_session.flush()

    summary = await service.event_result_summary(event.id)

    assert summary.majority_correct is False  # популяр o2 != winner o1
    assert summary.participation_pct is not None and summary.participation_pct > 0
