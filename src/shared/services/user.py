"""`UserService` — регистрация, поиск, блокировка."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import RegistryUnavailableError, UserNotAllowed
from ..external.registry import ExternalApiError, ExternalUserRegistryClient
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

    def __init__(
        self,
        session: AsyncSession,
        registry: ExternalUserRegistryClient | None = None,
    ) -> None:
        """`registry` обязателен только для `register_or_authenticate`.

        Для `touch_last_seen`/`block`/`unblock`/read-методов он не используется —
        тогда можно передавать `None` (например, в middleware `UserMiddleware`).
        """
        self._session = session
        self._users = UserRepository(session)
        self._reminders = ReminderSettingRepository(session)
        self._audit = AuditLogRepository(session)
        self._registry = registry

    async def register_or_authenticate(
        self,
        *,
        tg_user_id: int,
        phone: str,
        first_name: str,
        last_name: str | None = None,
        tg_username: str | None = None,
    ) -> User:
        if self._registry is None:
            raise RuntimeError("registry is required for register_or_authenticate")
        existing = await self._users.get_by_tg_user_id(tg_user_id)
        if existing is not None:
            await self._users.touch_last_seen(existing.id)
            await self._session.commit()
            return existing

        registry = self._registry
        try:
            verification = await registry.verify(phone)
        except ExternalApiError as exc:
            raise RegistryUnavailableError("registry unavailable") from exc

        if not verification.is_allowed:
            raise UserNotAllowed(reason=verification.reason)

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

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._users.get_by_id(user_id)

    async def get_by_tg_user_id(self, tg_user_id: int) -> User | None:
        return await self._users.get_by_tg_user_id(tg_user_id)
