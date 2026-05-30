"""Интеграционный тест для TASK-074: проверка рендера страницы деталей события.

Тест реально делает GET-запрос к FastAPI и проверяет, что ответ 200 (не 500).
Это регрессия на MissingGreenlet: шаблон form.html обращается к
event.category.name, event.created_by_admin.username и outcome.predictions,
которые должны быть eager-load'едены.

TASK-078: auth через dependency_overrides вместо подделки cookie.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from src.admin.app import app
from src.admin.auth.security import SESSION_COOKIE_NAME, create_session_token
from src.admin.deps import current_admin
from src.shared.config import settings
from src.shared.models import AdminUser, Category, Event, Outcome

pytestmark = pytest.mark.integration


def _uniq(prefix: str) -> str:
    """Уникальный человекочитаемый id для тестовых полей."""
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


@asynccontextmanager
async def _authed_client(admin: AdminUser) -> AsyncGenerator[TestClient, None]:
    """Создаёт TestClient с подменённым current_admin и валидной session-cookie.

    Паттерн из unit-тестов (`tests/unit/admin/test_events_handler.py`):
    1. Подменяем `current_admin` dependency — возвращаем админа из БД.
    2. Патчим `SessionLocal` в middleware, чтобы тот же админ доставался из БД.
    3. Строим валидную session-cookie через `create_session_token` с боевым секретом.
    """

    async def _get_current_admin() -> AdminUser:
        return admin

    # Подмена dependency для хендлера
    app.dependency_overrides[current_admin] = _get_current_admin

    # Фейковый SessionLocal для middleware — вернёт сессию, которая вернёт админа
    @asynccontextmanager
    async def _get_fake_session() -> AsyncGenerator[AsyncSession, None]:
        fake_session = AsyncMock(spec=AsyncSession)
        fake_session.get = AsyncMock(return_value=admin)
        yield fake_session

    # Middleware делает `SessionLocal()()` — нужен maker, который возвращает context manager
    fake_maker = MagicMock()
    fake_maker.return_value = _get_fake_session()

    # Патчим SessionLocal в middleware
    with patch("src.admin.auth.middleware.SessionLocal", fake_maker):
        token = create_session_token(admin_id=admin.id)
        client = TestClient(app, cookies={SESSION_COOKIE_NAME: token})
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio(loop_scope="session")
async def test_event_detail_returns_200_for_draft_without_outcomes() -> None:
    """TASK-074 regression: черновик без исходов должен рендериться с 200, а не 500.

    Сценарий:
    1. Создаём событие без исходов (draft).
    2. GET /events/{id} → ожидаем 200.
    3. До фиксации — 500 из-за MissingGreenlet (event.category и event.created_by_admin не загружены).
    """
    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sm() as session:
            admin = AdminUser(login=_uniq("admin"), password_hash="hash", full_name=None)
            session.add(admin)
            await session.flush()

            category = Category(name=_uniq("Cat"), slug=_uniq("cat"), sort_order=0, is_active=True)
            session.add(category)
            await session.flush()

            event = Event(
                category_id=category.id,
                title=_uniq("Event"),
                description=None,
                metadata_={},
                starts_at=datetime.now(tz=UTC) + timedelta(days=1),
                predictions_close_at=datetime.now(tz=UTC) + timedelta(days=1) - timedelta(minutes=10),
                created_by_admin_id=admin.id,
                is_published=False,
                is_archived=False,
            )
            session.add(event)
            await session.commit()

        async with _authed_client(admin) as client:
            response = client.get(f"/events/{event.id}")
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            # Проверяем, что ключевые данные присутствуют в ответе
            assert event.title in response.text
            assert category.name in response.text
            assert admin.login in response.text

        # Cleanup
        async with sm() as session:
            await session.delete(event)
            await session.delete(category)
            await session.delete(admin)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_event_detail_returns_200_for_published_with_outcomes() -> None:
    """TASK-074 regression: опубликованное событие с исходами тоже должно рендериться.

    Сценарий:
    1. Создаём опубликованное событие с 2+ исходами.
    2. GET /events/{id} → ожидаем 200.
    """
    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sm() as session:
            admin = AdminUser(login=_uniq("admin"), password_hash="hash", full_name=None)
            session.add(admin)
            await session.flush()

            category = Category(name=_uniq("Cat"), slug=_uniq("cat"), sort_order=0, is_active=True)
            session.add(category)
            await session.flush()

            event = Event(
                category_id=category.id,
                title=_uniq("Event"),
                description=None,
                metadata_={},
                starts_at=datetime.now(tz=UTC) + timedelta(days=1),
                predictions_close_at=datetime.now(tz=UTC) + timedelta(days=1) - timedelta(minutes=10),
                created_by_admin_id=admin.id,
                is_published=True,
                is_archived=False,
            )
            session.add(event)
            await session.flush()

            outcome1 = Outcome(event_id=event.id, label="Outcome 1", sort_order=0)
            outcome2 = Outcome(event_id=event.id, label="Outcome 2", sort_order=1)
            session.add(outcome1)
            session.add(outcome2)
            await session.commit()

        async with _authed_client(admin) as client:
            response = client.get(f"/events/{event.id}")
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            assert event.title in response.text
            # На дефолтной вкладке показывается только счётчик исходов
            assert "Исходы <span class=\"pv-muted\">· 2</span>" in response.text or "Исходы <span class=\"pv-muted\">·2</span>" in response.text or "Исходы · 2" in response.text

        # Cleanup
        async with sm() as session:
            await session.delete(outcome1)
            await session.delete(outcome2)
            await session.delete(event)
            await session.delete(category)
            await session.delete(admin)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_event_detail_returns_404_for_nonexistent() -> None:
    """GET /events/{nonexistent_id} → 404."""
    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sm() as session:
            admin = AdminUser(login=_uniq("admin"), password_hash="hash", full_name=None)
            session.add(admin)
            await session.commit()

        async with _authed_client(admin) as client:
            response = client.get("/events/99999")
            assert response.status_code == 404

        # Cleanup
        async with sm() as session:
            await session.delete(admin)
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_event_detail_result_tab_loads_without_error() -> None:
    """TASK-074: вкладка «Результат» тоже не должна стрелять MissingGreenlet.

    Сценарий:
    1. Создаём опубликованное событие с исходами.
    2. GET /events/{id}?tab=result → ожидаем 200.
    """
    engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sm() as session:
            admin = AdminUser(login=_uniq("admin"), password_hash="hash", full_name=None)
            session.add(admin)
            await session.flush()

            category = Category(name=_uniq("Cat"), slug=_uniq("cat"), sort_order=0, is_active=True)
            session.add(category)
            await session.flush()

            # Событие в прошлом — чтобы вкладка "Результат" была активна
            event = Event(
                category_id=category.id,
                title=_uniq("Event"),
                description=None,
                metadata_={},
                starts_at=datetime.now(tz=UTC) - timedelta(days=1),
                predictions_close_at=datetime.now(tz=UTC) - timedelta(days=1) - timedelta(minutes=10),
                created_by_admin_id=admin.id,
                is_published=True,
                is_archived=False,
            )
            session.add(event)
            await session.flush()

            outcome1 = Outcome(event_id=event.id, label="Outcome 1", sort_order=0)
            outcome2 = Outcome(event_id=event.id, label="Outcome 2", sort_order=1)
            session.add(outcome1)
            session.add(outcome2)
            await session.commit()

        async with _authed_client(admin) as client:
            response = client.get(f"/events/{event.id}?tab=result")
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text[:200]}"
            )
            assert "Итоговый исход" in response.text

        # Cleanup
        async with sm() as session:
            await session.delete(outcome1)
            await session.delete(outcome2)
            await session.delete(event)
            await session.delete(category)
            await session.delete(admin)
            await session.commit()
    finally:
        await engine.dispose()
