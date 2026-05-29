"""Routes раздела «Рассылки» админки (TASK-061)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.models import AdminUser
from src.shared.services import BroadcastService, CreateBroadcastDraft

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/broadcasts", tags=["broadcasts"])

PAGE_SIZE = 20


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@router.get("", response_class=HTMLResponse)
async def list_broadcasts(
    request: Request,
    page: int = Query(1, ge=1),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """История рассылок с пагинацией."""
    service = BroadcastService(session)
    items, total = await service.list_for_admin(page=page, page_size=PAGE_SIZE)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    return templates.TemplateResponse(
        request=request,
        name="broadcasts/list.html",
        context={
            "admin": admin,
            "items": items,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/new", response_class=HTMLResponse)
async def new_broadcast_form(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """Форма составления новой рассылки."""
    from src.shared.services import CategoryService

    service = BroadcastService(session)
    category_service = CategoryService(session)

    segments = service.list_segments()
    categories = await category_service.list_active()

    return templates.TemplateResponse(
        request=request,
        name="broadcasts/form.html",
        context={
            "admin": admin,
            "segments": segments,
            "categories": categories,
            "csrf_token": request.state.csrf_token,
        },
    )


@router.post("", response_class=HTMLResponse)
async def create_broadcast(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """Создаёт черновик и ставит рассылку в очередь."""
    form = await request.form()
    segment = str(form.get("segment", ""))
    category_id_str = str(form.get("category_id", ""))
    message_text = str(form.get("message_text", ""))

    category_id = int(category_id_str) if category_id_str else None

    dto = CreateBroadcastDraft(
        segment=segment,
        category_id=category_id,
        message_text=message_text,
        created_by_admin_id=admin.id,
    )

    service = BroadcastService(session)

    try:
        broadcast = await service.create_draft(dto)
        await service.enqueue(broadcast.id, admin)
    except Exception as exc:
        # Ошибка валидации — возвращаемся к форме с сообщением
        from src.shared.services import CategoryService

        category_service = CategoryService(session)
        segments = service.list_segments()
        categories = await category_service.list_active()

        return templates.TemplateResponse(
            request=request,
            name="broadcasts/form.html",
            context={
                "admin": admin,
                "segments": segments,
                "categories": categories,
                "csrf_token": request.state.csrf_token,
                "error": str(exc),
                "form_data": {
                    "segment": segment,
                    "category_id": category_id,
                    "message_text": message_text,
                },
            },
        )

    # Успех — редирект в историю с flash
    return templates.TemplateResponse(
        request=request,
        name="broadcasts/list.html",
        context={
            "admin": admin,
            "flash": "Рассылка поставлена в очередь",
            "items": [],
            "page": 1,
            "total_pages": 1,
            "total": 0,
        },
    )


@router.get("/preview-count", response_class=HTMLResponse)
async def preview_recipients_count(
    request: Request,
    segment: str = Query(...),
    category_id: int | None = Query(None),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
) -> HTMLResponse:
    """HTMX-фрагмент: показывает число получателей для выбранного сегмента."""
    service = BroadcastService(session)
    count = await service.count_recipients_for(segment, category_id)

    return templates.TemplateResponse(
        request=request,
        name="broadcasts/_preview_count.html",
        context={"count": count},
    )


@router.get("/preview-char-count")
async def preview_char_count(message: str = Query("")) -> HTMLResponse:
    """HTMX-фрагмент: показывает длину сообщения в байтах."""
    byte_count = len(message.encode("utf-8"))
    return HTMLResponse(f"<span>{byte_count}</span>")
