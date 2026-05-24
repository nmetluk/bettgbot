"""Routes аудит-лога админки (TASK-026, финал Этапа 3)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.models import AdminUser, AuditLog
from src.shared.repositories import AdminUserRepository
from src.shared.services import AuditService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/audit", tags=["audit"])

PAGE_SIZE = 50


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _parse_iso_date(value: str | None) -> datetime | None:
    """`datetime-local` присылает naive `YYYY-MM-DDTHH:MM`; добавляем UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@router.get("", response_class=HTMLResponse)
async def list_audit(
    request: Request,
    admin_id: int | None = Query(None),
    action: str | None = Query(None, min_length=1),
    since: str | None = Query(None),
    until: str | None = Query(None),
    page: int = Query(0, ge=0),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    since_dt = _parse_iso_date(since)
    until_dt = _parse_iso_date(until)

    service = AuditService(session)
    rows = await service.list(
        admin_id=admin_id,
        action=action,
        since=since_dt,
        until=until_dt,
        offset=page * PAGE_SIZE,
        limit=PAGE_SIZE,
    )
    total = await service.count(admin_id=admin_id, action=action, since=since_dt, until=until_dt)
    admins = await AdminUserRepository(session).list_all()

    return templates.TemplateResponse(
        request=request,
        name="audit/list.html",
        context={
            "admin": admin,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": PAGE_SIZE,
            "admins": admins,
            "selected_admin_id": admin_id,
            "selected_action": action or "",
            "selected_since": since or "",
            "selected_until": until or "",
        },
    )


@router.get("/{entry_id}/details", response_class=HTMLResponse)
async def details_fragment(
    request: Request,
    entry_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """HTMX-fragment: полный payload одной записи (JSON pretty-print)."""
    entry = await session.get(AuditLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="audit/_details.html",
        context={
            "entry": entry,
            "payload_pretty": json.dumps(entry.payload, indent=2, ensure_ascii=False),
        },
    )


@router.get("/{entry_id}/details/collapse", response_class=HTMLResponse)
async def details_collapse(
    request: Request,
    entry_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """HTMX-fragment: возврат в preview-режим (collapsed row)."""
    entry = await session.get(AuditLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="audit/_preview.html",
        context={"entry": entry},
    )
