"""AI model profile / binding / source-model admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai import ai_application
from apeiria.app.ai.operations import (
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)
from apeiria.webui.auth import require_auth
from apeiria.webui.routes.ai._auth_helpers import actor_username_from_claims

from .models_schemas import (
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIModelProfileUpsertRequest,
    AIModelRouteBindingItem,
    AIModelRouteBindingUpsertRequest,
    AIModelRouteItem,
    AIModelRouteMemberItem,
    AIModelRouteMemberUpsertRequest,
    AIModelRouteUpsertRequest,
    AISourceModelFetchRequest,
    AISourceModelItem,
    AISourceModelTestRequest,
    AISourceModelTestResult,
    AISourceModelUpsertRequest,
    to_ai_model_binding_item,
    to_ai_model_catalog_item,
    to_ai_model_profile_item,
    to_ai_model_route_binding_item,
    to_ai_model_route_item,
    to_ai_model_route_member_item,
    to_ai_source_model_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


@router.get("/sources/models", response_model=list[AISourceModelItem])
async def list_ai_source_models(
    _: Annotated[Any, Depends(require_auth)],
    source_id: Annotated[str, Query(min_length=1)],
) -> list[AISourceModelItem]:
    items = await ai_application.operations.list_source_models(source_id=source_id)
    return [to_ai_source_model_item(item) for item in items]


@router.post("/sources/models/fetch", response_model=list[AIModelCatalogItem])
async def fetch_ai_source_models(
    payload: AISourceModelFetchRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> list[AIModelCatalogItem]:
    try:
        items = await ai_application.operations.fetch_source_models(
            source_id=payload.source_id,
            preset_type=payload.preset_type,
            api_base=payload.api_base,
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
    _: Annotated[Any, Depends(require_auth)],
) -> AISourceModelTestResult:
    try:
        (
            model_identifier,
            content,
            tool_call_count,
        ) = await ai_application.operations.test_source_model(
            source_id=payload.source_id,
            preset_type=payload.preset_type,
            api_base=payload.api_base,
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
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AISourceModelItem:
    item = await ai_application.operations.create_source_model(
        source_id=payload.source_id,
        model_identifier=payload.model_identifier,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
        extra_params=payload.extra_params,
        capability_metadata=payload.capability_metadata,
        default_options=payload.default_options,
        capability_provenance=payload.capability_provenance,
        actor_username=actor_username_from_claims(session),
    )
    return to_ai_source_model_item(item)


@router.put("/sources/models", response_model=AISourceModelItem | None)
async def update_ai_source_model(
    payload: AISourceModelUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AISourceModelItem | None:
    if not payload.model_id:
        return None
    item = await ai_application.operations.update_source_model(
        model_id=payload.model_id,
        source_id=payload.source_id,
        model_identifier=payload.model_identifier,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
        extra_params=payload.extra_params,
        capability_metadata=payload.capability_metadata,
        default_options=payload.default_options,
        capability_provenance=payload.capability_provenance,
        actor_username=actor_username_from_claims(session),
    )
    return to_ai_source_model_item(item) if item is not None else None


@router.delete("/sources/models", response_model=bool)
async def delete_ai_source_model(
    session: Annotated["AuthSession", Depends(require_auth)],
    model_id: Annotated[str, Query(min_length=1)],
    source_id: Annotated[str | None, Query(max_length=64)] = None,
) -> bool:
    try:
        return await ai_application.operations.delete_source_model(
            model_id=model_id,
            source_id=source_id,
            actor_username=actor_username_from_claims(session),
        )
    except AISourceModelDeleteBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/model-profiles", response_model=list[AIModelProfileItem])
async def list_ai_model_profiles(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AIModelProfileItem]:
    profiles = await ai_application.operations.list_model_profiles()
    return [to_ai_model_profile_item(item) for item in profiles]


@router.put("/model-profiles", response_model=AIModelProfileItem | None)
async def upsert_ai_model_profile(
    payload: AIModelProfileUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AIModelProfileItem | None:
    item = (
        await ai_application.operations.update_model_profile(
            profile_id=payload.profile_id,
            name=payload.name,
            model_id=payload.model_id,
            task_class=payload.task_class,
            priority=payload.priority,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
        if payload.profile_id
        else await ai_application.operations.create_model_profile(
            name=payload.name,
            model_id=payload.model_id,
            task_class=payload.task_class,
            priority=payload.priority,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
    )
    return to_ai_model_profile_item(item) if item is not None else None


@router.get("/model-bindings", response_model=list[AIModelBindingItem])
async def list_ai_model_bindings(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AIModelBindingItem]:
    bindings = await ai_application.operations.list_model_bindings()
    return [to_ai_model_binding_item(item) for item in bindings]


@router.get("/model-routes", response_model=list[AIModelRouteItem])
async def list_ai_model_routes(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AIModelRouteItem]:
    routes = await ai_application.operations.list_model_routes()
    return [to_ai_model_route_item(item) for item in routes]


@router.put("/model-routes", response_model=AIModelRouteItem | None)
async def upsert_ai_model_route(
    payload: AIModelRouteUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AIModelRouteItem | None:
    item = (
        await ai_application.operations.update_model_route(
            route_id=payload.route_id,
            name=payload.name,
            task_class=payload.task_class,
            mode=payload.mode,
            algorithm=payload.algorithm,
            fallback_on_failure=payload.fallback_on_failure,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
        if payload.route_id
        else await ai_application.operations.create_model_route(
            name=payload.name,
            task_class=payload.task_class,
            mode=payload.mode,
            algorithm=payload.algorithm,
            fallback_on_failure=payload.fallback_on_failure,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
    )
    return to_ai_model_route_item(item) if item is not None else None


@router.delete("/model-routes", response_model=bool)
async def delete_ai_model_route(
    session: Annotated["AuthSession", Depends(require_auth)],
    route_id: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_application.operations.delete_model_route(
        route_id=route_id,
        actor_username=actor_username_from_claims(session),
    )


@router.get("/model-route-members", response_model=list[AIModelRouteMemberItem])
async def list_ai_model_route_members(
    _: Annotated[Any, Depends(require_auth)],
    route_id: Annotated[str | None, Query(min_length=1)] = None,
) -> list[AIModelRouteMemberItem]:
    members = await ai_application.operations.list_model_route_members(
        route_id=route_id
    )
    return [to_ai_model_route_member_item(item) for item in members]


@router.put(
    "/model-route-members",
    response_model=AIModelRouteMemberItem | None,
)
async def upsert_ai_model_route_member(
    payload: AIModelRouteMemberUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AIModelRouteMemberItem | None:
    item = (
        await ai_application.operations.update_model_route_member(
            route_member_id=payload.route_member_id,
            route_id=payload.route_id,
            profile_id=payload.profile_id,
            position=payload.position,
            weight=payload.weight,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
        if payload.route_member_id
        else await ai_application.operations.create_model_route_member(
            route_id=payload.route_id,
            profile_id=payload.profile_id,
            position=payload.position,
            weight=payload.weight,
            enabled=payload.enabled,
            actor_username=actor_username_from_claims(session),
        )
    )
    return to_ai_model_route_member_item(item) if item is not None else None


@router.delete("/model-route-members", response_model=bool)
async def delete_ai_model_route_member(
    session: Annotated["AuthSession", Depends(require_auth)],
    route_member_id: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_application.operations.delete_model_route_member(
        route_member_id=route_member_id,
        actor_username=actor_username_from_claims(session),
    )


@router.get("/model-route-bindings", response_model=list[AIModelRouteBindingItem])
async def list_ai_model_route_bindings(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AIModelRouteBindingItem]:
    bindings = await ai_application.operations.list_model_route_bindings()
    return [to_ai_model_route_binding_item(item) for item in bindings]


@router.put("/model-route-bindings", response_model=AIModelRouteBindingItem)
async def upsert_ai_model_route_binding(
    payload: AIModelRouteBindingUpsertRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AIModelRouteBindingItem:
    item = await ai_application.operations.upsert_model_route_binding(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        task_class=payload.task_class,
        route_id=payload.route_id,
        actor_username=actor_username_from_claims(session),
    )
    return to_ai_model_route_binding_item(item)


@router.delete("/model-route-bindings", response_model=bool)
async def delete_ai_model_route_binding(
    session: Annotated["AuthSession", Depends(require_auth)],
    scope_type: Annotated[str, Query(min_length=1)],
    scope_id: Annotated[str, Query(min_length=1)],
    task_class: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_application.operations.delete_model_route_binding(
        scope_type=scope_type,
        scope_id=scope_id,
        task_class=task_class,
        actor_username=actor_username_from_claims(session),
    )


__all__ = ["router"]
