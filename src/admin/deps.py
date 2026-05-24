"""DI dependencies для админки (TASK-020)."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from src.shared.models import AdminUser

__all__ = ["current_admin"]


async def current_admin(request: Request) -> AdminUser:
    """Достаёт текущего админа из `request.state` (положен `RequireAdminMiddleware`).

    Если middleware не отработал (баг конфигурации, prefer-fail-loud) — 401.
    На практике все приватные роуты пройдут через middleware, и dependency
    просто типизирует параметр для handler'а.
    """
    admin: AdminUser | None = getattr(request.state, "admin", None)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return admin
