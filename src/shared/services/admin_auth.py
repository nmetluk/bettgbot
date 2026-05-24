"""`AdminAuthService` — verify пароля, проверка `is_active`, обновление `last_login_at`.

Используется handler'ом `POST /login` админки (TASK-020). Никаких cookie/session
зависимостей — это чистая доменная логика, переиспользуемая в тестах.
"""

from __future__ import annotations

from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import AdminInactiveError, AdminInvalidCredentialsError
from ..models import AdminUser

__all__ = ["AdminAuthService"]


# Dummy bcrypt-hash (cost=12) для timing-attack mitigation. Сгенерирован один раз
# через `bcrypt.hashpw(b"unused", bcrypt.gensalt(rounds=12))`. Содержимое не важно,
# важно только время `checkpw` — оно должно совпадать с реальным сравнением,
# чтобы атакующий не различал «admin не найден» и «admin найден, пароль не подходит».
_DUMMY_HASH = b"$2b$12$SXY0ymA//Wbfo7c41.VABuElI5vkkqPpSpi3bWf4eZvFzDzVznqra"


class AdminAuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authenticate(self, *, login: str, password: str) -> AdminUser:
        """Verify login/password. Поднимает доменное исключение при неуспехе.

        - `AdminInvalidCredentialsError` — login не найден ИЛИ password неверный
          (одинаково, чтобы не давать enumeration-вектор).
        - `AdminInactiveError` — admin найден, password верный, но `is_active=False`.

        При успехе обновляет `last_login_at` и коммитит.
        """
        stmt = select(AdminUser).where(AdminUser.login == login)
        result = await self._session.execute(stmt)
        admin = result.scalar_one_or_none()
        if admin is None:
            # Dummy verify, чтобы время отклика не отличалось от случая
            # «admin найден, password не подходит» — анти-enumeration.
            bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
            raise AdminInvalidCredentialsError()

        if not bcrypt.checkpw(password.encode("utf-8"), admin.password_hash.encode("utf-8")):
            raise AdminInvalidCredentialsError()

        if not admin.is_active:
            raise AdminInactiveError(admin_id=admin.id)

        admin.last_login_at = datetime.now(tz=UTC)
        await self._session.commit()
        return admin
