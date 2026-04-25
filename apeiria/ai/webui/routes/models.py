"""AI model profile / binding / source-model admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.ai.admin.control_service import (
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
    ai_control_admin_service,
)
from apeiria.ai.webui.schemas import (
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIModelProfileUpsertRequest,
    AISourceModelFetchRequest,
    AISourceModelItem,
    AISourceModelTestRequest,
    AISourceModelTestResult,
    AISourceModelUpsertRequest,
)
from apeiria.ai.webui.support import (
    to_ai_model_binding_item,
    to_ai_model_catalog_item,
    to_ai_model_profile_item,
    to_ai_source_model_item,
)
from apeiria.webui.auth import require_control_panel

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/sources/models", response_model=list[AISourceModelItem])
async def list_ai_source_models(
    _: Annotated[Any, Depends(require_control_panel)],
    source_id: Annotated[str, Query(min_length=1)],
) -> list[AISourceModelItem]:
    items = await ai_control_admin_service.list_source_models(source_id=source_id)
    return [to_ai_source_model_item(item) for item in items]


@router.post("/sources/models/fetch", response_model=list[AIModelCatalogItem])
async def fetch_ai_source_models(
    payload: AISourceModelFetchRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelCatalogItem]:
    try:
        items = await ai_control_admin_service.fetch_source_models(
            source_id=payload.source_id,
            preset_type=payload.preset_type,
            api_base=payload.api_base,
            api_key_env_name=payload.api_key_env_name,
            api_key=payload.api_key,
            extra_config=payload.extra_config,
        )
    except AISourceModelFetchConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AISourceModelFetchUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return [to_ai_model_catalog_item(item) for item in items]


@router.post("/sources/models/test", response_model=AISourceModelTestResult)
async def test_ai_source_model(
    payload: AISourceModelTestRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AISourceModelTestResult:
    try:
        (
            model_identifier,
            content,
            tool_call_count,
        ) = await ai_control_admin_service.test_source_model(
            source_id=payload.source_id,
            preset_type=payload.preset_type,
            api_base=payload.api_base,
            api_key_env_name=payload.api_key_env_name,
            api_key=payload.api_key,
            extra_config=payload.extra_config,
            model_identifier=payload.model_identifier,
        )
    except AISourceModelTestConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except AISourceModelTestUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return AISourceModelTestResult(
        model_identifier=model_identifier,
        content=content,
        tool_call_count=tool_call_count,
    )


@router.post("/sources/models", response_model=AISourceModelItem)
async def create_ai_source_model(
    payload: AISourceModelUpsertRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AISourceModelItem:
    item = await ai_control_admin_service.create_source_model(
        source_id=payload.source_id,
        model_identifier=payload.model_identifier,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
        extra_params=payload.extra_params,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_source_model_item(item)


@router.put("/sources/models", response_model=AISourceModelItem | None)
async def update_ai_source_model(
    payload: AISourceModelUpsertRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AISourceModelItem | None:
    if not payload.model_id:
        return None
    item = await ai_control_admin_service.update_source_model(
        model_id=payload.model_id,
        source_id=payload.source_id,
        model_identifier=payload.model_identifier,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
        extra_params=payload.extra_params,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_source_model_item(item) if item is not None else None


@router.delete("/sources/models", response_model=bool)
async def delete_ai_source_model(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    model_id: Annotated[str, Query(min_length=1)],
    source_id: Annotated[str | None, Query(max_length=64)] = None,
) -> bool:
    try:
        return await ai_control_admin_service.delete_source_model(
            model_id=model_id,
            source_id=source_id,
            actor_username=_actor_username_from_claims(session),
        )
    except AISourceModelDeleteBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/model-profiles", response_model=list[AIModelProfileItem])
async def list_ai_model_profiles(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelProfileItem]:
    profiles = await ai_control_admin_service.list_model_profiles()
    return [to_ai_model_profile_item(item) for item in profiles]


@router.put("/model-profiles", response_model=AIModelProfileItem | None)
async def upsert_ai_model_profile(
    payload: AIModelProfileUpsertRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIModelProfileItem | None:
    item = (
        await ai_control_admin_service.update_model_profile(
            profile_id=payload.profile_id,
            name=payload.name,
            model_id=payload.model_id,
            task_class=payload.task_class,
            priority=payload.priority,
            enabled=payload.enabled,
            fallback_profile_id=payload.fallback_profile_id,
            actor_username=_actor_username_from_claims(session),
        )
        if payload.profile_id
        else await ai_control_admin_service.create_model_profile(
            name=payload.name,
            model_id=payload.model_id,
            task_class=payload.task_class,
            priority=payload.priority,
            enabled=payload.enabled,
            fallback_profile_id=payload.fallback_profile_id,
            actor_username=_actor_username_from_claims(session),
        )
    )
    return to_ai_model_profile_item(item) if item is not None else None


@router.get("/model-bindings", response_model=list[AIModelBindingItem])
async def list_ai_model_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelBindingItem]:
    bindings = await ai_control_admin_service.list_model_bindings()
    return [to_ai_model_binding_item(item) for item in bindings]


__all__ = ["router"]
