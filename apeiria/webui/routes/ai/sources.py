"""AI source admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai import ai_application
from apeiria.app.ai.operations import (
    AISourceDeleteBlockedError,
)
from apeiria.webui.auth import require_auth
from apeiria.webui.routes.ai._auth_helpers import actor_username_from_claims

from .sources_schemas import (
    AISourceItem,
    AISourcePresetItem,
    AISourceUpsertRequest,
    to_ai_source_item,
    to_ai_source_preset_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


@router.get("/source-presets", response_model=list[AISourcePresetItem])
async def list_ai_source_presets(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AISourcePresetItem]:
    return [
        to_ai_source_preset_item(item)
        for item in ai_application.operations.list_source_presets()
    ]


@router.get("/sources", response_model=list[AISourceItem])
async def list_ai_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AISourceItem]:
    items = await ai_application.operations.list_sources()
    return [to_ai_source_item(item) for item in items]


@router.post("/sources", response_model=AISourceItem)
async def create_ai_source(
    payload: AISourceUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AISourceItem:
    item = await ai_application.operations.create_source(
        name=payload.name,
        capability_type=payload.capability_type,
        preset_type=payload.preset_type,
        api_base=payload.api_base,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        custom_headers=payload.custom_headers,
        extra_config=payload.extra_config,
        api_key_action=payload.api_key_action,
        api_keys=payload.api_keys,
        adapter_kind=payload.adapter_kind,
        capability_metadata=payload.capability_metadata,
        default_options=payload.default_options,
        capability_provenance=payload.capability_provenance,
        actor_username=actor_username_from_claims(session),
    )
    return to_ai_source_item(item)


@router.put("/sources", response_model=AISourceItem | None)
async def update_ai_source(
    payload: AISourceUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AISourceItem | None:
    if not payload.source_id:
        return None
    item = await ai_application.operations.update_source(
        source_id=payload.source_id,
        name=payload.name,
        capability_type=payload.capability_type,
        preset_type=payload.preset_type,
        api_base=payload.api_base,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        custom_headers=payload.custom_headers,
        extra_config=payload.extra_config,
        api_key_action=payload.api_key_action,
        api_keys=payload.api_keys,
        adapter_kind=payload.adapter_kind,
        capability_metadata=payload.capability_metadata,
        default_options=payload.default_options,
        capability_provenance=payload.capability_provenance,
        actor_username=actor_username_from_claims(session),
    )
    return to_ai_source_item(item) if item is not None else None


@router.delete("/sources", response_model=bool)
async def delete_ai_source(
    session: Annotated["AuthSession", Depends(require_auth)],
    source_id: Annotated[str, Query(min_length=1)],
) -> bool:
    try:
        return await ai_application.operations.delete_source(
            source_id=source_id,
            actor_username=actor_username_from_claims(session),
        )
    except AISourceDeleteBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


__all__ = ["router"]
