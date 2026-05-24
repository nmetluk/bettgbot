"""Routes CRUD событий админки (TASK-022).

Вкладка «Данные» формы редактирования + публикация/снятие. Вкладки «Исходы»
и «Результат» — TASK-023 и TASK-024 (сейчас disabled-ссылки в шаблоне).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.exceptions import (
    EventAlreadyHasResultError,
    EventNotEnoughOutcomesError,
    EventNotFoundError,
    OutcomeNotForEventError,
)
from src.shared.models import AdminUser
from src.shared.repositories.event import AdminEventPeriod, AdminEventStatus
from src.shared.services import CategoryService, EventService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/events", tags=["events"])

PAGE_SIZE = 50


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _parse_dt(raw: str) -> datetime | None:
    """`datetime-local` присылает `YYYY-MM-DDTHH:MM` без TZ; None при битом вводе."""
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_metadata(raw: str) -> dict[str, Any] | None:
    """`{}` если пусто, dict при валидном JSON, None при ошибке."""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


@router.get("", response_class=HTMLResponse)
async def list_events(
    request: Request,
    category_id: int | None = Query(None),
    status: AdminEventStatus = Query("all"),
    period: AdminEventPeriod = Query("all"),
    page: int = Query(0, ge=0),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    event_service = EventService(session)
    rows = await event_service.list_admin_with_counts(
        category_id=category_id,
        status=status,
        period=period,
        offset=page * PAGE_SIZE,
        limit=PAGE_SIZE,
    )
    total = await event_service.count_admin(category_id=category_id, status=status, period=period)
    cat_rows = await CategoryService(session).list_all_with_counts(include_inactive=True)
    return templates.TemplateResponse(
        request=request,
        name="events/list.html",
        context={
            "admin": admin,
            "rows": rows,
            "total": total,
            "page": page,
            "categories": [c for c, _ in cat_rows],
            "selected_category_id": category_id,
            "selected_status": status,
            "selected_period": period,
            "page_size": PAGE_SIZE,
        },
    )


def _render_form_with_error(
    request: Request,
    *,
    admin: AdminUser,
    csrf_protect: CsrfProtect,
    event: Any,
    categories: list[Any],
    form_action: str,
    error: str,
    status_code: int = 400,
) -> HTMLResponse:
    """Re-render формы при ошибке POST — генерирует CSRF (middleware POST не покрывает)."""
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    request.state.csrf_token = csrf_token
    response = templates.TemplateResponse(
        request=request,
        name="events/form.html",
        context={
            "admin": admin,
            "event": event,
            "categories": categories,
            "form_action": form_action,
            "error": error,
            "active_tab": "data",
        },
        status_code=status_code,
    )
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get("/new", response_class=HTMLResponse)
async def new_form(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    cat_rows = await CategoryService(session).list_all_with_counts(include_inactive=False)
    categories = [c for c, _ in cat_rows]
    return templates.TemplateResponse(
        request=request,
        name="events/form.html",
        context={
            "admin": admin,
            "event": None,
            "categories": categories,
            "form_action": "/events",
            "error": None,
            "active_tab": "data",
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_event(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(...),
    starts_at: str = Form(...),
    predictions_close_at: str = Form(...),
    metadata: str = Form("{}"),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> Response:
    await csrf_protect.validate_csrf(request)

    cat_rows = await CategoryService(session).list_all_with_counts(include_inactive=False)
    categories = [c for c, _ in cat_rows]

    starts_at_dt = _parse_dt(starts_at)
    close_at_dt = _parse_dt(predictions_close_at)
    metadata_dict = _parse_metadata(metadata)
    if starts_at_dt is None or close_at_dt is None or metadata_dict is None:
        return _render_form_with_error(
            request,
            admin=admin,
            csrf_protect=csrf_protect,
            event={
                "title": title,
                "description": description,
                "category_id": category_id,
                "starts_at": None,
                "predictions_close_at": None,
                "metadata_": metadata,
            },
            categories=categories,
            form_action="/events",
            error="Неверный формат даты или metadata-JSON.",
        )

    event = await EventService(session).create_event(
        category_id=category_id,
        title=title,
        description=description or None,
        metadata=metadata_dict,
        starts_at=starts_at_dt,
        predictions_close_at=close_at_dt,
        by_admin_id=admin.id,
    )
    return RedirectResponse(url=f"/events/{event.id}", status_code=status.HTTP_302_FOUND)


@router.get("/{event_id}", response_class=HTMLResponse)
async def edit_form(
    request: Request,
    event_id: int,
    tab: str = Query("data"),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    event = await EventService(session).get_event(event_id, with_outcomes=True)
    if event is None:
        raise HTTPException(status_code=404)
    cat_rows = await CategoryService(session).list_all_with_counts(include_inactive=True)
    return templates.TemplateResponse(
        request=request,
        name="events/form.html",
        context={
            "admin": admin,
            "event": event,
            "categories": [c for c, _ in cat_rows],
            "form_action": f"/events/{event_id}",
            "error": None,
            "active_tab": tab,
        },
    )


@router.post("/{event_id}", response_class=HTMLResponse)
async def update_event(
    request: Request,
    event_id: int,
    title: str = Form(...),
    description: str = Form(""),
    category_id: int = Form(...),
    starts_at: str = Form(...),
    predictions_close_at: str = Form(...),
    metadata: str = Form("{}"),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> Response:
    await csrf_protect.validate_csrf(request)

    starts_at_dt = _parse_dt(starts_at)
    close_at_dt = _parse_dt(predictions_close_at)
    metadata_dict = _parse_metadata(metadata)
    if starts_at_dt is None or close_at_dt is None or metadata_dict is None:
        # 400 без рендера полной формы (упрощение): редирект на edit с error-param.
        return RedirectResponse(
            url=f"/events/{event_id}?error=invalid_input",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        await EventService(session).update_event(
            event_id,
            by_admin_id=admin.id,
            title=title,
            description=description or None,
            category_id=category_id,
            starts_at=starts_at_dt,
            predictions_close_at=close_at_dt,
            metadata_=metadata_dict,
        )
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)


@router.post("/{event_id}/publish")
async def publish_event(
    request: Request,
    event_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    try:
        await EventService(session).publish_event(event_id, by_admin_id=admin.id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    except EventNotEnoughOutcomesError:
        return RedirectResponse(
            url=f"/events/{event_id}?error=not_enough_outcomes",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)


@router.post("/{event_id}/result")
async def set_result(
    request: Request,
    event_id: int,
    outcome_id: int = Form(...),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    """Транзакционная фиксация итога; помечает все прогнозы as correct/incorrect."""
    await csrf_protect.validate_csrf(request)
    try:
        marked = await EventService(session).set_result(
            event_id=event_id, outcome_id=outcome_id, by_admin_id=admin.id
        )
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    except EventAlreadyHasResultError:
        return RedirectResponse(
            url=f"/events/{event_id}?tab=result&error=already_set",
            status_code=status.HTTP_302_FOUND,
        )
    except OutcomeNotForEventError:
        return RedirectResponse(
            url=f"/events/{event_id}?tab=result&error=outcome_not_for_event",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=f"/events/{event_id}?tab=result&success=result_set&marked={marked}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{event_id}/unpublish")
async def unpublish_event(
    request: Request,
    event_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    try:
        await EventService(session).unpublish_event(event_id, by_admin_id=admin.id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    return RedirectResponse(url=f"/events/{event_id}", status_code=status.HTTP_302_FOUND)
