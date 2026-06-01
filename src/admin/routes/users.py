"""Routes раздела «Пользователи» админки (TASK-025)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.models import AdminUser
from src.shared.services import PredictionService, StatsService, UserService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/users", tags=["users"])

PAGE_SIZE = 50


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("", response_class=HTMLResponse)
async def list_users(
    request: Request,
    query: str | None = Query(None, min_length=1),
    page: int = Query(0, ge=0),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    service = UserService(session)
    rows = await service.list_admin_with_counts(
        query=query, offset=page * PAGE_SIZE, limit=PAGE_SIZE
    )
    total = await service.count_for_admin(query=query)
    return templates.TemplateResponse(
        request=request,
        name="users/list.html",
        context={
            "admin": admin,
            "rows": rows,
            "total": total,
            "page": page,
            "query": query or "",
            "page_size": PAGE_SIZE,
        },
    )


@router.get("/{user_id}", response_class=HTMLResponse)
async def user_detail(
    request: Request,
    user_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    user = await UserService(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404)
    predictions = await PredictionService(session).list_all_by_user_for_admin(
        user_id, offset=0, limit=100
    )
    correct, total, percent = await StatsService(session).user_stats(user_id)
    return templates.TemplateResponse(
        request=request,
        name="users/detail.html",
        context={
            "admin": admin,
            "user": user,
            "predictions": predictions,
            "stats_correct": correct,
            "stats_total": total,
            "stats_percent": percent,
        },
    )


@router.post("/{user_id}/block")
async def block_user(
    request: Request,
    user_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404)
    await service.block(user_id, by_admin_id=admin.id)
    return RedirectResponse(
        url=f"/users/{user_id}?success=blocked",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{user_id}/unblock")
async def unblock_user(
    request: Request,
    user_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    service = UserService(session)
    user = await service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404)
    await service.unblock(user_id, by_admin_id=admin.id)
    return RedirectResponse(
        url=f"/users/{user_id}?success=unblocked",
        status_code=status.HTTP_302_FOUND,
    )
