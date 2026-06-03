"""Integration-тесты аналитических методов `PredictionRepository` (TASK-059)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import Prediction
from src.shared.repositories import PredictionRepository
from tests.integration.conftest import make_category, make_event, make_outcome, make_user

pytestmark = pytest.mark.integration


@pytest.fixture(name="now")
def fixture_now() -> datetime:
    """Фиксированное опорное «сейчас» для детерминированных окон.

    Используем инъекцию reference_now в repo/service (добавлено в TASK-102),
    поэтому тест полностью герметичен — не зависит от реального utcnow().
    Выбрана дата после проблемного 2026-06-03, чтобы -25d и т.п. стабильно
    попадали в 30-дневное окно.
    """
    return datetime(2026, 6, 3, 12, 0, tzinfo=UTC)


async def test_daily_prediction_counts_30_day_window(session: AsyncSession, now: datetime) -> None:
    """Динамика по дням за 30 дней: группировка и заполнение нулей."""
    # Создадим прогнозы только в 3 дня из 30
    repo = PredictionRepository(session)
    user = await make_user(session)

    # День -25 (в пределах окна)
    event1 = await make_event(session, created_at=now - timedelta(days=25))
    outcome1 = await make_outcome(session, event1.id)
    pred1 = Prediction(
        user_id=user.id,
        event_id=event1.id,
        outcome_id=outcome1.id,
        created_at=now - timedelta(days=25),
    )
    session.add(pred1)

    # День -10
    event2 = await make_event(session, created_at=now - timedelta(days=10))
    outcome2 = await make_outcome(session, event2.id)
    pred2 = Prediction(
        user_id=user.id,
        event_id=event2.id,
        outcome_id=outcome2.id,
        created_at=now - timedelta(days=10),
    )
    session.add(pred2)

    # Сегодня
    event3 = await make_event(session, created_at=now)
    outcome3 = await make_outcome(session, event3.id)
    pred3 = Prediction(
        user_id=user.id,
        event_id=event3.id,
        outcome_id=outcome3.id,
        created_at=now,
    )
    session.add(pred3)

    # Прогноз вне окна (40 дней назад) — не должен попасть
    event_old = await make_event(session, created_at=now - timedelta(days=40))
    outcome_old = await make_outcome(session, event_old.id)
    pred_old = Prediction(
        user_id=user.id,
        event_id=event_old.id,
        outcome_id=outcome_old.id,
        created_at=now - timedelta(days=40),
    )
    session.add(pred_old)

    await session.flush()

    rows = await repo.daily_prediction_counts(days=30, reference_now=now)

    # Репозиторий возвращает только дни с данными
    assert len(rows) == 3

    rows_dict = dict(rows)
    assert rows_dict[(now - timedelta(days=25)).strftime("%Y-%m-%d")] == 1
    assert rows_dict[(now - timedelta(days=10)).strftime("%Y-%m-%d")] == 1
    assert rows_dict[now.strftime("%Y-%m-%d")] == 1

    # Старый прогноз не в окне
    old_date = (now - timedelta(days=40)).strftime("%Y-%m-%d")
    assert old_date not in rows_dict

    # Проверим, что сервис заполняет нулями
    from src.shared.services import StatsService

    service = StatsService(session)
    daily = await service.daily_prediction_counts(days=30, reference_now=now)
    assert len(daily) == 30  # Сервис заполняет нулями
    zero_days = [d for d in daily if d.count == 0]
    assert len(zero_days) == 27  # 30 - 3 дня с прогнозами


async def test_category_accuracy_calculation(session: AsyncSession) -> None:
    """Точность по категориям: correct/resolved*100."""
    repo = PredictionRepository(session)

    # Категория A: 3/4 = 75%
    cat_a = await make_category(session, name="Category A", slug="cat-a")
    event_a1 = await make_event(session, category=cat_a)
    outcome_a1 = await make_outcome(session, event_a1.id)
    event_a2 = await make_event(session, category=cat_a)
    outcome_a2 = await make_outcome(session, event_a2.id)
    event_a3 = await make_event(session, category=cat_a)
    outcome_a3 = await make_outcome(session, event_a3.id)
    event_a4 = await make_event(session, category=cat_a)
    outcome_a4 = await make_outcome(session, event_a4.id)

    # Категория B: 1/2 = 50%
    cat_b = await make_category(session, name="Category B", slug="cat-b")
    event_b1 = await make_event(session, category=cat_b)
    outcome_b1 = await make_outcome(session, event_b1.id)
    event_b2 = await make_event(session, category=cat_b)
    outcome_b2 = await make_outcome(session, event_b2.id)

    # Категория C: только неразрешённые (должна быть исключена)
    cat_c = await make_category(session, name="Category C", slug="cat-c")
    event_c = await make_event(session, category=cat_c)
    outcome_c = await make_outcome(session, event_c.id)

    # Добавляем прогнозы для категории A: 3 верных из 4 (разные пользователи)
    user = await make_user(session)
    for event, outcome, is_correct in [
        (event_a1, outcome_a1, True),
        (event_a2, outcome_a2, True),
        (event_a3, outcome_a3, True),
        (event_a4, outcome_a4, False),
    ]:
        pred = Prediction(
            user_id=user.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=is_correct,
        )
        session.add(pred)
        await session.flush()
        # Удаляем прогноз, чтобы следующий прошел (чтобы обойти unique constraint)
        session.expunge(pred)

    # Категория B: 1 верный из 2 (разные пользователи)
    for event, outcome, is_correct in [
        (event_b1, outcome_b1, True),
        (event_b2, outcome_b2, False),
    ]:
        user_b = await make_user(session)
        pred = Prediction(
            user_id=user_b.id,
            event_id=event.id,
            outcome_id=outcome.id,
            is_correct=is_correct,
        )
        session.add(pred)
        await session.flush()
        session.expunge(pred)

    # Категория C: неразрешённый прогноз
    user_c = await make_user(session)
    pred_c = Prediction(
        user_id=user_c.id,
        event_id=event_c.id,
        outcome_id=outcome_c.id,
        is_correct=None,
    )
    session.add(pred_c)

    await session.flush()

    rows = await repo.category_accuracy()

    # Категория C исключена (нет разрешённых)
    assert len(rows) == 2

    rows_dict = {
        (cat_id, slug): (correct, resolved, acc)
        for cat_id, name, slug, correct, resolved, acc in rows
    }

    # Проверим категорию A
    key_a = (cat_a.id, "cat-a")
    assert key_a in rows_dict
    correct_a, resolved_a, acc_a = rows_dict[key_a]
    assert correct_a == 3
    assert resolved_a == 4
    assert abs(acc_a - 75.0) < 0.1

    # Проверим категорию B
    key_b = (cat_b.id, "cat-b")
    assert key_b in rows_dict
    correct_b, resolved_b, acc_b = rows_dict[key_b]
    assert correct_b == 1
    assert resolved_b == 2
    assert abs(acc_b - 50.0) < 0.1


async def test_funnel_metrics(session: AsyncSession) -> None:
    """Воронка: всего незаблокированных vs сделавших прогноз."""
    repo = PredictionRepository(session)

    # Создаём пользователей
    u_with_pred = await make_user(session, first_name="WithPrediction")
    _ = await make_user(session, first_name="NoPrediction")
    _ = await make_user(session, first_name="Blocked", is_blocked=True)

    # Добавляем прогноз только одному
    event = await make_event(session)
    outcome = await make_outcome(session, event.id)
    pred = Prediction(user_id=u_with_pred.id, event_id=event.id, outcome_id=outcome.id)
    session.add(pred)

    await session.flush()

    total, with_pred = await repo.funnel_metrics()

    # total = 2 (u_with_pred + u_without_pred), u_blocked исключён
    assert total == 2
    # with_pred = 1 (только u_with_pred)
    assert with_pred == 1

    # Через сервис проверим конверсию
    from src.shared.services import StatsService

    service = StatsService(session)
    funnel = await service.funnel_metrics()
    assert funnel.total_users == 2
    assert funnel.users_with_predictions == 1
    assert abs(funnel.conversion_percent - 50.0) < 0.1


async def test_top_events_by_prediction_count(session: AsyncSession) -> None:
    """Топ событий: группировка по event_id, сортировка по count."""
    repo = PredictionRepository(session)

    # Событие 1: 10 прогнозов
    event1 = await make_event(session, title="Event 1")
    outcome1 = await make_outcome(session, event1.id)

    # Событие 2: 5 прогнозов
    event2 = await make_event(session, title="Event 2")
    outcome2 = await make_outcome(session, event2.id)

    # Событие 3: 7 прогнозов
    event3 = await make_event(session, title="Event 3")
    outcome3 = await make_outcome(session, event3.id)

    # Добавляем прогнозы (разные пользователи для каждого события)
    for _ in range(10):
        user = await make_user(session)
        pred = Prediction(user_id=user.id, event_id=event1.id, outcome_id=outcome1.id)
        session.add(pred)

    for _ in range(5):
        user = await make_user(session)
        pred = Prediction(user_id=user.id, event_id=event2.id, outcome_id=outcome2.id)
        session.add(pred)

    for _ in range(7):
        user = await make_user(session)
        pred = Prediction(user_id=user.id, event_id=event3.id, outcome_id=outcome3.id)
        session.add(pred)

    await session.flush()

    rows = await repo.top_events(limit=10)

    # Проверим сортировку: Event 1 (10), Event 3 (7), Event 2 (5)
    assert len(rows) == 3
    assert rows[0][0] == event1.id
    assert rows[0][3] == 10  # prediction_count

    assert rows[1][0] == event3.id
    assert rows[1][3] == 7

    assert rows[2][0] == event2.id
    assert rows[2][3] == 5

    # Проверим, что названия и slug корректны
    assert rows[0][1] == "Event 1"
    # Slug берётся из slug категории, созданной make_event
    assert isinstance(rows[0][2], str)  # slug - это строка
