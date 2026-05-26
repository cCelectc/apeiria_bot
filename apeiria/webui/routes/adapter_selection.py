"""Adapter selection routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.app.plugins.adapter_selection import (
    AdapterSelectionRequest,
    adapter_selection_service,
)
from apeiria.webui.auth import require_control_panel, require_owner
from apeiria.webui.schemas.adapter_selection import (
    AdapterSelectionEnableRequest,
    AdapterSelectionItem,
    AdapterSelectionQueryParams,
    AdapterSelectionResponse,
    to_adapter_selection_item,
    to_adapter_selection_response,
)

router = APIRouter()


@router.get("", response_model=AdapterSelectionResponse)
async def get_adapter_selection(
    params: Annotated[AdapterSelectionQueryParams, Depends()],
    _: Annotated[Any, Depends(require_control_panel)],
) -> AdapterSelectionResponse:
    state = await adapter_selection_service.get_selection(
        AdapterSelectionRequest(
            search=params.search,
            source=params.source,
            category=params.category,
            sort=params.sort,
            unenabled_only=params.unenabled_only,
            page=params.page,
            per_page=params.per_page,
        )
    )
    return to_adapter_selection_response(state)


@router.post("/enable", response_model=AdapterSelectionItem)
async def enable_adapter(
    payload: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_owner)],
) -> AdapterSelectionItem:
    try:
        item = adapter_selection_service.enable_adapter(payload.module_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_adapter_selection_item(item)


@router.post("/disable", response_model=AdapterSelectionItem)
async def disable_adapter(
    payload: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_owner)],
) -> AdapterSelectionItem:
    item = adapter_selection_service.disable_adapter(payload.module_name)
    if item is None:
        raise HTTPException(status_code=404, detail="adapter is not enabled")
    return to_adapter_selection_item(item)
