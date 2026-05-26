"""HTMX-routes для inline CRUD исходов событий (TASK-023).

Все handler'ы возвращают HTML-фрагменты для `hx-swap` в `#outcomes-container`.
Корневая загрузка вкладки — GET `/events/{id}/outcomes` (list-fragment).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.exceptions import (
    EventNotFoundError,
    OutcomeInUseError,
    OutcomeNotForEventError,
)
from src.shared.models import AdminUser
from src.shared.services import EventService

from .._helpers import set_fresh_csrf_token
from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(
    prefix="/events/{event_id}/outcomes",
    tags=["outcomes"],
)


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def _list_response(
    request: Request,
    session: AsyncSession,
    event_id: int,
    csrf_protect: CsrfProtect,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Загружает event с outcomes и рендерит fragment-list. Re-используется write-handler'ами."""
    event = await EventService(session).get_event(event_id, with_outcomes=True)
    if event is None:
        raise HTTPException(status_code=404)
    response = templates.TemplateResponse(
        request=request,
        name="outcomes/_list.html",
        context={
            "event_id": event_id,
            "outcomes": event.outcomes,
            "error": error,
        },
        status_code=status_code,
    )
    set_fresh_csrf_token(request, response, csrf_protect)
    return response


@router.get("", response_class=HTMLResponse)
async def list_fragment(
    request: Request,
    event_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    return await _list_response(request, session, event_id, csrf_protect)


@router.get("/new", response_class=HTMLResponse)
async def new_form_fragment(
    request: Request,
    event_id: int,
    admin: AdminUser = Depends(current_admin),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="outcomes/_form.html",
        context={"event_id": event_id, "outcome": None},
    )


@router.post("", response_class=HTMLResponse)
async def create(
    request: Request,
    event_id: int,
    label: str = Form(...),
    sort_order: int = Form(0),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    await csrf_protect.validate_csrf(request)
    try:
        await EventService(session).add_outcome(
            event_id=event_id,
            label=label,
            sort_order=sort_order,
            by_admin_id=admin.id,
        )
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    return await _list_response(request, session, event_id, csrf_protect)


@router.get("/{outcome_id}/edit", response_class=HTMLResponse)
async def edit_form_fragment(
    request: Request,
    event_id: int,
    outcome_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    event = await EventService(session).get_event(event_id, with_outcomes=True)
    if event is None:
        raise HTTPException(status_code=404)
    outcome = next((o for o in event.outcomes if o.id == outcome_id), None)
    if outcome is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request=request,
        name="outcomes/_form.html",
        context={"event_id": event_id, "outcome": outcome},
    )


@router.post("/{outcome_id}", response_class=HTMLResponse)
async def update(
    request: Request,
    event_id: int,
    outcome_id: int,
    label: str = Form(...),
    sort_order: int = Form(0),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    """POST вместо PUT — HTMX `<form>` шлёт POST по умолчанию."""
    await csrf_protect.validate_csrf(request)
    try:
        await EventService(session).update_outcome(
            outcome_id=outcome_id,
            event_id=event_id,
            by_admin_id=admin.id,
            label=label,
            sort_order=sort_order,
        )
    except OutcomeNotForEventError:
        raise HTTPException(status_code=404) from None
    return await _list_response(request, session, event_id, csrf_protect)


@router.post("/{outcome_id}/delete", response_class=HTMLResponse)
async def delete(
    request: Request,
    event_id: int,
    outcome_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    await csrf_protect.validate_csrf(request)
    try:
        await EventService(session).delete_outcome(
            outcome_id=outcome_id, event_id=event_id, by_admin_id=admin.id
        )
    except OutcomeNotForEventError:
        raise HTTPException(status_code=404) from None
    except OutcomeInUseError:
        return await _list_response(
            request,
            session,
            event_id,
            csrf_protect,
            error=f"Нельзя удалить исход #{outcome_id}: на него есть прогнозы.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return await _list_response(request, session, event_id, csrf_protect)
