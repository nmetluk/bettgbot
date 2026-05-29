"""`BroadcastRepository` — запросы к таблицам `broadcast` и `broadcast_delivery`.

Не управляет транзакциями. Идемпотентность доставки через UNIQUE constraint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Broadcast, BroadcastDelivery, Category, Event, Prediction, User

__all__ = ["BroadcastRepository"]


class BroadcastRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_draft(
        self,
        *,
        segment: str,
        category_id: int | None = None,
        message_text: str,
        created_by_admin_id: int,
    ) -> Broadcast:
        """Создаёт черновик рассылки."""
        broadcast = Broadcast(
            segment=segment,
            category_id=category_id,
            message_text=message_text,
            status="draft",
            created_by_admin_id=created_by_admin_id,
        )
        self._session.add(broadcast)
        await self._session.flush()
        return broadcast

    async def enqueue(self, broadcast_id: int) -> None:
        """Ставит рассылку в очередь (draft → queued)."""
        await self._session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id, Broadcast.status == "draft")
            .values(status="queued")
        )

    async def claim_next_queued(self) -> Broadcast | None:
        """Атомарно забирает одну queued рассылку и переводит в sending.

        Использует SELECT FOR UPDATE SKIP LOCKED для избежания гонок
        при max_instances > 1 (хотя у нас max_instances=1).
        """
        stmt = (
            select(Broadcast)
            .where(Broadcast.status == "queued")
            .order_by(Broadcast.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        broadcast = result.scalar_one_or_none()
        if broadcast is None:
            return None

        # Обновляем статус и started_at
        broadcast.status = "sending"
        broadcast.started_at = datetime.now(tz=UTC)
        await self._session.flush()
        return broadcast

    async def recipients_for(self, segment: str, category_id: int | None = None) -> list[int]:
        """Возвращает список user_id для заданного сегмента.

        Сегменты:
        - `all`: все неблокированные пользователи
        - `active`: is_blocked=False AND last_seen_at >= now() - 30 days
        - `category`: distinct user_id с прогнозами в событиях данной категории
        """
        cutoff_active = datetime.now(tz=UTC) - timedelta(days=30)

        if segment == "all":
            stmt = select(User.id).where(User.is_blocked.is_(False)).order_by(User.id)
        elif segment == "active":
            stmt = (
                select(User.id)
                .where(
                    User.is_blocked.is_(False),
                    User.last_seen_at >= cutoff_active,
                )
                .order_by(User.id)
            )
        elif segment == "category":
            # distinct user_id через Prediction → Event → Category
            stmt = (
                select(Prediction.user_id)
                .join(Event, Prediction.event_id == Event.id)
                .join(Category, Event.category_id == Category.id)
                .where(
                    Category.id == category_id,
                    User.is_blocked.is_(False),
                )
                .distinct()
                .order_by(Prediction.user_id)
            )
        else:
            return []

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_recipients_for(self, segment: str, category_id: int | None = None) -> int:
        """Считает число получателей для сегмента (для предпросмотра в форме)."""
        cutoff_active = datetime.now(tz=UTC) - timedelta(days=30)

        if segment == "all":
            stmt = select(func.count(User.id)).where(User.is_blocked.is_(False))
        elif segment == "active":
            stmt = select(func.count(User.id)).where(
                User.is_blocked.is_(False),
                User.last_seen_at >= cutoff_active,
            )
        elif segment == "category":
            stmt = (
                select(func.count(func.distinct(Prediction.user_id)))
                .join(Event, Prediction.event_id == Event.id)
                .join(Category, Event.category_id == Category.id)
                .where(
                    Category.id == category_id,
                    User.is_blocked.is_(False),
                )
            )
        else:
            return 0

        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def record_delivery(self, broadcast_id: int, user_id: int) -> bool:
        """Записывает факт доставки. Возвращает True если запись новая.

        Идемпотентность через UNIQUE constraint на (broadcast_id, user_id).
        """
        stmt = (
            pg_insert(BroadcastDelivery)
            .values(broadcast_id=broadcast_id, user_id=user_id)
            .on_conflict_do_nothing(index_elements=["broadcast_id", "user_id"])
        )
        result = await self._session.execute(stmt)
        # rowcount > 0 значит вставка прошла (conflict не был)
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def increment_sent(self, broadcast_id: int) -> None:
        """Инкремент счётчика успешно отправленных."""
        await self._session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(sent_count=Broadcast.sent_count + 1)
        )

    async def increment_failed(self, broadcast_id: int) -> None:
        """Инкремент счётчика failed (user blocked/bot banned, etc)."""
        await self._session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(failed_count=Broadcast.failed_count + 1)
        )

    async def mark_done(self, broadcast_id: int) -> None:
        """Завершает рассылку (sending → done + finished_at)."""
        await self._session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(status="done", finished_at=func.now())
        )

    async def mark_failed(self, broadcast_id: int) -> None:
        """Отмечает рассылку как failed (критический сбой, например 0 получателей)."""
        await self._session.execute(
            update(Broadcast)
            .where(Broadcast.id == broadcast_id)
            .values(status="failed", finished_at=func.now())
        )

    async def get_by_id(self, broadcast_id: int) -> Broadcast | None:
        """Возвращает рассылку по ID с eager loading категории."""
        stmt = (
            select(Broadcast)
            .options(selectinload(Broadcast.category))
            .where(Broadcast.id == broadcast_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_admin(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Broadcast], int]:
        """Возвращает список рассылок для админки с пагинацией.

        Возвращает (items, total_count). Новые сверху.
        """
        # Считаем total
        count_stmt = select(func.count(Broadcast.id))
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Забираем страницу
        stmt = (
            select(Broadcast)
            .options(selectinload(Broadcast.category))
            .order_by(Broadcast.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update_total_recipients(self, broadcast_id: int, count: int) -> None:
        """Обновляет total_recipients (вызывается при enqueue)."""
        await self._session.execute(
            update(Broadcast).where(Broadcast.id == broadcast_id).values(total_recipients=count)
        )
