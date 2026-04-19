"""AI admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai.admin.service import (
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
    ai_admin_service,
)
from apeiria.app.ai.tools.models import AIToolPolicy
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import (
    to_ai_capability_item,
    to_ai_capability_preview_item,
    to_ai_chat_message_item,
    to_ai_future_task_item,
    to_ai_memory_item,
    to_ai_model_binding_item,
    to_ai_model_catalog_item,
    to_ai_model_profile_item,
    to_ai_person_profile_item,
    to_ai_persona_binding_item,
    to_ai_persona_item,
    to_ai_recent_target_item,
    to_ai_relationship_event_item,
    to_ai_relationship_state_item,
    to_ai_session_item,
    to_ai_session_prompt_preview_item,
    to_ai_skill_item,
    to_ai_source_item,
    to_ai_source_model_item,
    to_ai_source_preset_item,
    to_ai_tool_execution_item,
    to_ai_tool_intent_preview_item,
    to_ai_tool_item,
    to_ai_tool_policy_binding_item,
    to_ai_tool_policy_preview_item,
)
from apeiria.interfaces.http.schemas.ai_models import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AICapabilityPreviewRequest,
    AIChatMessageItem,
    AIFutureTaskItem,
    AIMemoryBulkActionRequest,
    AIMemoryBulkActionResult,
    AIMemoryBulkIgnoreRequest,
    AIMemoryCreateRequest,
    AIMemoryDeleteResult,
    AIMemoryItem,
    AIMemoryToggleIgnoredRequest,
    AIMemoryUpdateRequest,
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIModelProfileUpsertRequest,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIPersonaUpsertRequest,
    AIPersonProfileItem,
    AIPersonProfileUpdateRequest,
    AIRecentTargetItem,
    AIRelationshipEventItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
    AISessionItem,
    AISessionPromptPreviewItem,
    AISkillItem,
    AISourceItem,
    AISourceModelFetchRequest,
    AISourceModelItem,
    AISourceModelTestRequest,
    AISourceModelTestResult,
    AISourceModelUpsertRequest,
    AISourcePresetItem,
    AISourceUpsertRequest,
    AIToolExecutionItem,
    AIToolIntentPreviewItem,
    AIToolIntentPreviewRequest,
    AIToolItem,
    AIToolPolicyBindingCreateRequest,
    AIToolPolicyBindingItem,
    AIToolPolicyBindingUpdateRequest,
    AIToolPolicyPreviewItem,
    AIToolPolicyPreviewRequest,
)

if TYPE_CHECKING:
    from apeiria.shared.principal import AuthSession

router = APIRouter()


def _actor_username_from_claims(session: AuthSession) -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/source-presets", response_model=list[AISourcePresetItem])
async def list_ai_source_presets(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AISourcePresetItem]:
    return [
        to_ai_source_preset_item(item)
        for item in ai_admin_service.list_source_presets()
    ]


@router.get("/sources", response_model=list[AISourceItem])
async def list_ai_sources(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AISourceItem]:
    items = await ai_admin_service.list_sources()
    return [to_ai_source_item(item) for item in items]


@router.post("/sources", response_model=AISourceItem)
async def create_ai_source(
    payload: AISourceUpsertRequest,
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> AISourceItem:
    item = await ai_admin_service.create_source(
        name=payload.name,
        capability_type=payload.capability_type,
        preset_type=payload.preset_type,
        api_base=payload.api_base,
        api_key_env_name=payload.api_key_env_name,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        custom_headers=payload.custom_headers,
        extra_config=payload.extra_config,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_source_item(item)


@router.put("/sources", response_model=AISourceItem | None)
async def update_ai_source(
    payload: AISourceUpsertRequest,
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> AISourceItem | None:
    if not payload.source_id:
        return None
    item = await ai_admin_service.update_source(
        source_id=payload.source_id,
        name=payload.name,
        capability_type=payload.capability_type,
        preset_type=payload.preset_type,
        api_base=payload.api_base,
        api_key_env_name=payload.api_key_env_name,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        custom_headers=payload.custom_headers,
        extra_config=payload.extra_config,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_source_item(item) if item is not None else None


@router.delete("/sources", response_model=bool)
async def delete_ai_source(
    session: Annotated[AuthSession, Depends(require_control_panel)],
    source_id: Annotated[str, Query(min_length=1)],
) -> bool:
    try:
        return await ai_admin_service.delete_source(
            source_id=source_id,
            actor_username=_actor_username_from_claims(session),
        )
    except AISourceDeleteBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/sources/models", response_model=list[AISourceModelItem])
async def list_ai_source_models(
    _: Annotated[Any, Depends(require_control_panel)],
    source_id: Annotated[str, Query(min_length=1)],
) -> list[AISourceModelItem]:
    items = await ai_admin_service.list_source_models(source_id=source_id)
    return [to_ai_source_model_item(item) for item in items]


@router.post("/sources/models/fetch", response_model=list[AIModelCatalogItem])
async def fetch_ai_source_models(
    payload: AISourceModelFetchRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelCatalogItem]:
    try:
        items = await ai_admin_service.fetch_source_models(
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
        ) = await ai_admin_service.test_source_model(
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
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> AISourceModelItem:
    item = await ai_admin_service.create_source_model(
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
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> AISourceModelItem | None:
    if not payload.model_id:
        return None
    item = await ai_admin_service.update_source_model(
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
    session: Annotated[AuthSession, Depends(require_control_panel)],
    model_id: Annotated[str, Query(min_length=1)],
    source_id: Annotated[str | None, Query(max_length=64)] = None,
) -> bool:
    try:
        return await ai_admin_service.delete_source_model(
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
    profiles = await ai_admin_service.list_model_profiles()
    return [to_ai_model_profile_item(item) for item in profiles]


@router.put("/model-profiles", response_model=AIModelProfileItem | None)
async def upsert_ai_model_profile(
    payload: AIModelProfileUpsertRequest,
    session: Annotated[AuthSession, Depends(require_control_panel)],
) -> AIModelProfileItem | None:
    item = (
        await ai_admin_service.update_model_profile(
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
        else await ai_admin_service.create_model_profile(
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
    bindings = await ai_admin_service.list_model_bindings()
    return [to_ai_model_binding_item(item) for item in bindings]




@router.get("/recent-targets", response_model=list[AIRecentTargetItem])
async def list_ai_recent_targets(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRecentTargetItem]:
    targets = await ai_admin_service.list_recent_targets(limit=limit)
    return [to_ai_recent_target_item(item) for item in targets]


@router.get("/scenes", response_model=list[AISessionItem])
async def list_ai_scenes(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AISessionItem]:
    conversations = await ai_admin_service.list_recent_sessions(limit=limit)
    return [to_ai_session_item(item) for item in conversations]


@router.get("/scenes/turns", response_model=list[AIChatMessageItem])
async def list_ai_scene_turns(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIChatMessageItem]:
    turns = await ai_admin_service.list_scene_turns(
        scene_id=scene_id,
        limit=limit,
    )
    return [to_ai_chat_message_item(item) for item in turns]


@router.get(
    "/scenes/prompt-preview",
    response_model=AISessionPromptPreviewItem | None,
)
async def get_ai_scene_prompt_preview(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
    turn_limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AISessionPromptPreviewItem | None:
    preview = await ai_admin_service.build_scene_prompt_preview(
        scene_id=scene_id,
        turn_limit=turn_limit,
    )
    if preview is None:
        return None
    return to_ai_session_prompt_preview_item(preview)








from apeiria.interfaces.http.routes.ai_future_tasks_routes import router as _future_tasks_router
from apeiria.interfaces.http.routes.ai_person_profiles_routes import router as _person_profiles_router
from apeiria.interfaces.http.routes.ai_personas_routes import router as _personas_router
from apeiria.interfaces.http.routes.ai_relationships_routes import router as _relationships_router

router.include_router(_future_tasks_router)
router.include_router(_person_profiles_router)
router.include_router(_personas_router)
router.include_router(_relationships_router)
from apeiria.interfaces.http.routes.ai_memories_routes import router as _memories_router
from apeiria.interfaces.http.routes.ai_tools_routes import router as _tools_router

router.include_router(_memories_router)
router.include_router(_tools_router)
