"""Routes CRUD категорий админки (TASK-021)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db import SessionLocal
from src.shared.exceptions import (
    CategoryHasEventsError,
    CategoryNotFoundError,
    CategorySlugConflictError,
)
from src.shared.models import AdminUser, Category
from src.shared.services import CategoryService

from ..app import templates
from ..deps import current_admin

__all__ = ["router"]

router = APIRouter(prefix="/categories", tags=["categories"])


async def _session_dep() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _render_form(
    request: Request,
    *,
    admin: AdminUser,
    csrf_protect: CsrfProtect,
    category: Category | dict[str, object] | None,
    form_action: str,
    error: str | None,
    status_code: int = 200,
) -> HTMLResponse:
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse(
        request=request,
        name="categories/form.html",
        context={
            "admin": admin,
            "category": category,
            "csrf_token": csrf_token,
            "error": error,
            "form_action": form_action,
        },
        status_code=status_code,
    )
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get("", response_class=HTMLResponse)
async def list_categories(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    rows = await CategoryService(session).list_all_with_counts(include_inactive=True)
    # csrf_token нужен для delete-кнопок и logout-формы в sidebar.
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = templates.TemplateResponse(
        request=request,
        name="categories/list.html",
        context={"admin": admin, "rows": rows, "csrf_token": csrf_token},
    )
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get("/new", response_class=HTMLResponse)
async def new_form(
    request: Request,
    admin: AdminUser = Depends(current_admin),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    return _render_form(
        request,
        admin=admin,
        csrf_protect=csrf_protect,
        category=None,
        form_action="/categories",
        error=None,
    )


@router.post("", response_class=HTMLResponse)
async def create_category(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> Response:
    await csrf_protect.validate_csrf(request)
    try:
        await CategoryService(session).create_category(
            name=name,
            slug=slug,
            sort_order=sort_order,
            is_active=is_active,
            by_admin_id=admin.id,
        )
    except CategorySlugConflictError as exc:
        return _render_form(
            request,
            admin=admin,
            csrf_protect=csrf_protect,
            category={
                "name": name,
                "slug": slug,
                "sort_order": sort_order,
                "is_active": is_active,
            },
            form_action="/categories",
            error=f"Категория со slug «{exc.slug}» уже существует.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)


@router.get("/{category_id}", response_class=HTMLResponse)
async def edit_form(
    request: Request,
    category_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> HTMLResponse:
    category = await CategoryService(session).get_by_id(category_id)
    if category is None:
        raise HTTPException(status_code=404)
    return _render_form(
        request,
        admin=admin,
        csrf_protect=csrf_protect,
        category=category,
        form_action=f"/categories/{category_id}",
        error=None,
    )


@router.post("/{category_id}", response_class=HTMLResponse)
async def update_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    sort_order: int = Form(0),
    is_active: bool = Form(False),
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> Response:
    await csrf_protect.validate_csrf(request)
    try:
        await CategoryService(session).update_category(
            category_id=category_id,
            by_admin_id=admin.id,
            name=name,
            slug=slug,
            sort_order=sort_order,
            is_active=is_active,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    except CategorySlugConflictError as exc:
        return _render_form(
            request,
            admin=admin,
            csrf_protect=csrf_protect,
            category={
                "id": category_id,
                "name": name,
                "slug": slug,
                "sort_order": sort_order,
                "is_active": is_active,
            },
            form_action=f"/categories/{category_id}",
            error=f"Категория со slug «{exc.slug}» уже существует.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)


@router.post("/{category_id}/delete")
async def delete_category(
    request: Request,
    category_id: int,
    admin: AdminUser = Depends(current_admin),
    session: AsyncSession = Depends(_session_dep),
    csrf_protect: CsrfProtect = Depends(),
) -> RedirectResponse:
    await csrf_protect.validate_csrf(request)
    try:
        await CategoryService(session).delete_category(category_id, by_admin_id=admin.id)
    except CategoryNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    except CategoryHasEventsError:
        # Flash через query-string: list.html рендерит alert.
        return RedirectResponse(
            url=f"/categories?error=has_events&category_id={category_id}",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(url="/categories", status_code=status.HTTP_302_FOUND)
