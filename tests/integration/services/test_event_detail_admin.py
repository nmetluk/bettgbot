"""Интеграционный тест для TASK-074: проверка рендера страницы деталей события.

Тест реально делает GET-запрос к FastAPI и проверяет, что ответ 200 (не 500).
Это регрессия на MissingGreenlet: шаблон form.html обращается к
event.category.name, event.created_by_admin.username и outcome.predictions,
которые должны быть eager-load'едены.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.admin.app import app
from src.admin.auth.security import create_session_token
from tests.integration.conftest import make_admin, make_category, make_event

pytestmark = pytest.mark.integration


async def _create_authenticated_session(session: AsyncSession) -> str:
    """Создаёт админа и возвращает валидный session token."""
    admin = await make_admin(session, login="test_admin", password_hash="hash")
    return create_session_token(admin_id=admin.id)


@pytest.mark.asyncio
async def test_event_detail_returns_200_for_draft_without_outcomes(
    nested_session: AsyncSession,
) -> None:
    """TASK-074 regression: черновик без исходов должен рендериться с 200, а не 500.

    Сценарий:
    1. Создаём событие без исходов (draft).
    2. GET /events/{id} → ожидаем 200.
    3. До фиксации — 500 из-за MissingGreenlet (event.category и event.created_by_admin не загружены).
    """
    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=False,
    )
    await nested_session.commit()

    token = await _create_authenticated_session(nested_session)
    client = TestClient(app, cookies={"session": token})

    response = client.get(f"/events/{event.id}")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:200]}"
    )
    # Проверяем, что ключевые данные присутствуют в ответе
    assert event.title in response.text
    assert category.name in response.text
    assert admin.login in response.text


@pytest.mark.asyncio
async def test_event_detail_returns_200_for_published_with_outcomes(
    nested_session: AsyncSession,
) -> None:
    """TASK-074 regression: опубликованное событие с исходами тоже должно рендериться.

    Сценарий:
    1. Создаём опубликованное событие с 2+ исходами.
    2. GET /events/{id} → ожидаем 200.
    """
    from tests.integration.conftest import make_outcome

    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=True,
    )
    await make_outcome(nested_session, event_id=event.id, label="Outcome 1")
    await make_outcome(nested_session, event_id=event.id, label="Outcome 2")
    await nested_session.commit()

    token = await _create_authenticated_session(nested_session)
    client = TestClient(app, cookies={"session": token})

    response = client.get(f"/events/{event.id}")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:200]}"
    )
    assert event.title in response.text
    assert "Outcome 1" in response.text
    assert "Outcome 2" in response.text


@pytest.mark.asyncio
async def test_event_detail_returns_404_for_nonexistent(nested_session: AsyncSession) -> None:
    """GET /events/{nonexistent_id} → 404."""
    token = await _create_authenticated_session(nested_session)
    client = TestClient(app, cookies={"session": token})

    response = client.get("/events/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_event_detail_result_tab_loads_without_error(nested_session: AsyncSession) -> None:
    """TASK-074: вкладка «Результат» тоже не должна стрелять MissingGreenlet.

    Сценарий:
    1. Создаём опубликованное событие с исходами.
    2. GET /events/{id}?tab=result → ожидаем 200.
    """
    from tests.integration.conftest import make_outcome

    admin = await make_admin(nested_session)
    category = await make_category(nested_session)
    # Создаём событие в прошлом (закрыто для фиксации итога)
    starts_at = datetime.now(tz=UTC) - timedelta(days=1)
    event = await make_event(
        nested_session,
        category=category,
        admin=admin,
        is_published=True,
        starts_at=starts_at,
        predictions_close_at=starts_at - timedelta(hours=1),  # <= starts_at для CHECK constraint
    )
    await make_outcome(nested_session, event_id=event.id, label="Outcome 1")
    await make_outcome(nested_session, event_id=event.id, label="Outcome 2")
    await nested_session.commit()

    token = await _create_authenticated_session(nested_session)
    client = TestClient(app, cookies={"session": token})

    response = client.get(f"/events/{event.id}?tab=result")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:200]}"
    )
    assert "Итоговый исход" in response.text
