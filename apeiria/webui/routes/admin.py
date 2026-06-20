from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Integer

from apeiria.webui.admin_registry import get as _get_svc
from apeiria.webui.admin_registry import list_types as _list_resource_types
from apeiria.webui.routes.deps import get_db, require_auth
from apeiria.webui.schemas.admin import (
    AdminListResponse,
    DeleteBatchRequest,
    DeleteBatchResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()


def _coerce_pk(pk_raw: str, pk_field: Any) -> Any:
    col = pk_field
    if isinstance(col, Integer) or (
        hasattr(col, "type") and isinstance(getattr(col, "type", None), Integer)
    ):
        try:
            return int(pk_raw)
        except (ValueError, TypeError):
            return pk_raw
    return pk_raw


# ── GET /{resource} ──────────────────────────────────────────


@router.get("/{resource}")
async def list_resource(
    resource: str,
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
    page: int = 1,
    size: int = 50,
) -> AdminListResponse:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    items, total = await svc.list(db, page=page, size=size)
    pages = max(1, (total + size - 1) // size) if total > 0 else 1
    return AdminListResponse(
        items=items, total=total, page=page, size=size, pages=pages
    )


# ── GET /{resource}/{pk} ──────────────────────────────────────


@router.get("/{resource}/{pk:path}")
async def get_resource(
    resource: str,
    pk: str,
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> Any:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    pk_column = getattr(svc.model, svc.pk_field, None)
    pk_value = _coerce_pk(pk, pk_column)

    item = await svc.get(db, pk_value)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return item


# ── POST /{resource} ─────────────────────────────────────────


@router.post("/{resource}", status_code=201)
async def create_resource(
    resource: str,
    body: dict[str, Any],
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> Any:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    if not svc.allow_create:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    create_cls = getattr(svc, "create_cls", None)
    if create_cls is None:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = create_cls.model_validate(body)
    return await svc.create(db, data)


# ── PATCH /{resource}/{pk} ────────────────────────────────────


@router.patch("/{resource}/{pk:path}")
async def update_resource(
    resource: str,
    pk: str,
    body: dict[str, Any],
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> Any:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    if not svc.allow_update:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    update_cls = getattr(svc, "update_cls", None)
    if update_cls is None:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = update_cls.model_validate(body)
    pk_column = getattr(svc.model, svc.pk_field, None)
    pk_value = _coerce_pk(pk, pk_column)

    item = await svc.update(db, pk_value, data.model_dump(exclude_unset=True))
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return item


# ── DELETE /{resource}/{pk} ───────────────────────────────────


@router.delete("/{resource}/{pk:path}", status_code=204)
async def delete_resource(
    resource: str,
    pk: str,
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> None:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    if not svc.allow_delete:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    pk_column = getattr(svc.model, svc.pk_field, None)
    pk_value = _coerce_pk(pk, pk_column)

    ok = await svc.delete(db, pk_value)
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")


# ── POST /{resource}/delete-batch ─────────────────────────────


@router.post("/{resource}/delete-batch")
async def delete_batch_resource(
    resource: str,
    body: DeleteBatchRequest,
    _: Annotated[Any, Depends(require_auth)],
    db: Annotated["AsyncSession", Depends(get_db)],
) -> DeleteBatchResponse:
    try:
        svc = _get_svc(resource)
    except KeyError:
        raise HTTPException(status_code=404, detail="resource_not_found") from None

    if not svc.allow_batch_delete:
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED)

    pk_column = getattr(svc.model, svc.pk_field, None)
    pk_values = [_coerce_pk(v, pk_column) for v in body.ids]

    deleted, failed = await svc.delete_batch(db, pk_values)
    return DeleteBatchResponse(deleted=deleted, failed=failed)


# ── GET / ─────────────────────────────────────────────────────


@router.get("")
async def list_resource_types(
    _: Annotated[Any, Depends(require_auth)],
) -> list[str]:
    return _list_resource_types()
