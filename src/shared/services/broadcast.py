"""`BroadcastService` — создание рассылок и бизнес-логика."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import DomainError
from ..models import AdminUser, Broadcast
from ..repositories import AuditLogRepository, BroadcastRepository, CategoryRepository

__all__ = [
    "BroadcastSegment",
    "BroadcastService",
    "CreateBroadcastDraft",
]

_MAX_MESSAGE_LENGTH = 4096  # Telegram лимит для текстового сообщения


@dataclass(frozen=True, slots=True)
class BroadcastSegment:
    """Описание сегмента для UI."""

    value: str
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class CreateBroadcastDraft:
    """DTO для создания черновика рассылки."""

    segment: str
    category_id: int | None
    message_text: str
    created_by_admin_id: int


class BroadcastService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._broadcasts = BroadcastRepository(session)
        self._categories = CategoryRepository(session)
        self._audit = AuditLogRepository(session)

    _SEGMENTS: ClassVar[list[BroadcastSegment]] = [
        BroadcastSegment("all", "Все пользователи", "Всем неблокированным пользователям"),
        BroadcastSegment(
            "active",
            "Активные",
            "Тем, кто был онлайн за последние 30 дней",
        ),
        BroadcastSegment(
            "category",
            "По категории",
            "Пользователям, делавшим прогнозы в событиях категории",
        ),
    ]

    @classmethod
    def list_segments(cls) -> list[BroadcastSegment]:
        """Список доступных сегментов."""
        return cls._SEGMENTS

    async def get_by_id(self, broadcast_id: int) -> Broadcast | None:
        """Возвращает рассылку по ID."""
        return await self._broadcasts.get_by_id(broadcast_id)

    async def list_for_admin(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[list[Broadcast], int]:
        """Список рассылок для админки с пагинацией."""
        offset = (page - 1) * page_size
        items, total = await self._broadcasts.list_for_admin(limit=page_size, offset=offset)
        return items, total

    async def count_recipients_for(self, segment: str, category_id: int | None = None) -> int:
        """Считает число получателей для сегмента (для предпросмотра)."""
        return await self._broadcasts.count_recipients_for(segment, category_id)

    async def create_draft(self, dto: CreateBroadcastDraft) -> Broadcast:
        """Создаёт черновик рассылки с валидацией."""
        # Валидация текста
        if not dto.message_text or not dto.message_text.strip():
            raise _BroadcastError("Текст сообщения не может быть пустым")
        if len(dto.message_text.encode("utf-8")) > _MAX_MESSAGE_LENGTH:
            raise _BroadcastError(
                f"Текст сообщения превышает {_MAX_MESSAGE_LENGTH} байт (лимит Telegram)"
            )

        # Валидация сегмента
        valid_segments = {s.value for s in self._SEGMENTS}
        if dto.segment not in valid_segments:
            raise _BroadcastError(f"Неверный сегмент: {dto.segment}")

        # Для segment=category проверяем существование категории
        if dto.segment == "category":
            if dto.category_id is None:
                raise _BroadcastError("Для сегмента 'category' необходимо указать категорию")
            category = await self._categories.get_by_id(dto.category_id)
            if category is None:
                raise _BroadcastError("Категория не найдена")
            if not category.is_active:
                raise _BroadcastError("Категория неактивна")

        broadcast = await self._broadcasts.create_draft(
            segment=dto.segment,
            category_id=dto.category_id,
            message_text=dto.message_text,
            created_by_admin_id=dto.created_by_admin_id,
        )
        await self._session.commit()
        await self._session.refresh(broadcast)
        return broadcast

    async def enqueue(self, broadcast_id: int, admin: AdminUser) -> Broadcast:
        """Ставит рассылку в очередь.

        Вызывается из админки при отправке. Подсчитывает total_recipients
        и пишет audit-запись.
        """
        broadcast = await self._broadcasts.get_by_id(broadcast_id)
        if broadcast is None:
            raise _BroadcastError("Рассылка не найдена")
        if broadcast.status != "draft":
            raise _BroadcastError("Рассылку можно отправить только из статуса draft")

        # Подсчитываем получателей
        recipient_count = await self._broadcasts.count_recipients_for(
            segment=broadcast.segment, category_id=broadcast.category_id
        )
        await self._broadcasts.update_total_recipients(broadcast_id, recipient_count)

        # Гард: пустой сегмент → сразу done (нечего отправлять)
        if recipient_count == 0:
            await self._broadcasts.mark_done(broadcast_id)
        else:
            await self._broadcasts.enqueue(broadcast_id)

        # Audit
        await self._audit.add(
            admin_id=admin.id,
            action="broadcast.enqueue",
            payload={
                "broadcast_id": broadcast_id,
                "segment": broadcast.segment,
                "category_id": broadcast.category_id,
                "total_recipients": recipient_count,
            },
        )

        await self._session.commit()
        await self._session.refresh(broadcast)
        return broadcast


class _BroadcastError(DomainError):
    """Доменная ошибка операций с рассылками."""

    def _reason(self) -> str:
        return self.args[0] if self.args else "Ошибка операции с рассылкой"
