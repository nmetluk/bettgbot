"""`UserService` — регистрация, поиск, блокировка."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..repositories import (
    AuditLogRepository,
    ReminderSettingRepository,
    UserRepository,
)

__all__ = ["UserService"]


_DEFAULT_REMINDER_OFFSETS = [1440, 60]


class UserService:
    """Доменная логика регистрации, блокировки и поиска пользователей."""

    def __init__(self, session: AsyncSession) -> None:
        """UserService без внешнего реестра (открытая регистрация с 2026-06-01).

        Регистрация разрешена любому, кто прислал свой контакт (кроме is_blocked).
        """
        self._session = session
        self._users = UserRepository(session)
        self._reminders = ReminderSettingRepository(session)
        self._audit = AuditLogRepository(session)

    async def register_or_authenticate(
        self,
        *,
        tg_user_id: int,
        phone: str,
        first_name: str,
        last_name: str | None = None,
        tg_username: str | None = None,
    ) -> User:
        """Открытая регистрация: любой с собственным контактом (кроме is_blocked в handler).

        Создаёт User + дефолтные напоминания сразу после проверки «ещё нет».
        """
        existing = await self._users.get_by_tg_user_id(tg_user_id)
        if existing is not None:
            await self._users.touch_last_seen(existing.id)
            await self._session.commit()
            return existing

        user = await self._users.create(
            tg_user_id=tg_user_id,
            phone=phone,
            tg_username=tg_username,
            first_name=first_name,
            last_name=last_name,
        )
        await self._reminders.upsert(
            user_id=user.id,
            enabled=True,
            offsets_minutes=list(_DEFAULT_REMINDER_OFFSETS),
        )
        await self._session.commit()
        return user

    async def touch_last_seen(self, user_id: int) -> None:
        await self._users.touch_last_seen(user_id)
        await self._session.commit()

    async def block(self, user_id: int, by_admin_id: int) -> None:
        await self._users.set_blocked(user_id, True)
        await self._audit.add(
            admin_id=by_admin_id,
            action="user.block",
            payload={"user_id": user_id},
        )
        await self._session.commit()

    async def unblock(self, user_id: int, by_admin_id: int) -> None:
        await self._users.set_blocked(user_id, False)
        await self._audit.add(
            admin_id=by_admin_id,
            action="user.unblock",
            payload={"user_id": user_id},
        )
        await self._session.commit()

    async def list_for_admin(
        self, *, query: str | None = None, offset: int = 0, limit: int = 50
    ) -> Sequence[User]:
        return await self._users.list_for_admin(query=query, offset=offset, limit=limit)

    async def count_for_admin(self, *, query: str | None = None) -> int:
        return await self._users.count_for_admin(query=query)

    async def list_admin_with_counts(
        self,
        *,
        query: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[tuple[User, int]]:
        return await self._users.list_for_admin_with_prediction_counts(
            query=query, offset=offset, limit=limit
        )

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._users.get_by_id(user_id)

    async def get_by_tg_user_id(self, tg_user_id: int) -> User | None:
        return await self._users.get_by_tg_user_id(tg_user_id)
