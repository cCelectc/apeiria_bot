"""AI admin routes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai.admin.service import (
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
    to_ai_conversation_item,
    to_ai_conversation_prompt_preview_item,
    to_ai_conversation_turn_item,
    to_ai_future_task_item,
    to_ai_memory_item,
    to_ai_model_binding_item,
    to_ai_model_catalog_item,
    to_ai_model_profile_item,
    to_ai_persona_binding_item,
    to_ai_persona_item,
    to_ai_recent_target_item,
    to_ai_relationship_state_item,
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
    AIConversationItem,
    AIConversationPromptPreviewItem,
    AIConversationTurnItem,
    AIFutureTaskItem,
    AIMemoryCreateRequest,
    AIMemoryDeleteResult,
    AIMemoryItem,
    AIMemoryUpdateRequest,
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIModelProfileUpsertRequest,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIPersonaUpsertRequest,
    AIRecentTargetItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
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

router = APIRouter()


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
    _: Annotated[Any, Depends(require_control_panel)],
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
    )
    return to_ai_source_item(item)


@router.put("/sources", response_model=AISourceItem | None)
async def update_ai_source(
    payload: AISourceUpsertRequest,
    _: Annotated[Any, Depends(require_control_panel)],
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
    )
    return to_ai_source_item(item) if item is not None else None


@router.delete("/sources", response_model=bool)
async def delete_ai_source(
    _: Annotated[Any, Depends(require_control_panel)],
    source_id: Annotated[str, Query(min_length=1)],
) -> bool:
    return await ai_admin_service.delete_source(source_id=source_id)


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
    _: Annotated[Any, Depends(require_control_panel)],
) -> AISourceModelItem:
    item = await ai_admin_service.create_source_model(
        source_id=payload.source_id,
        model_identifier=payload.model_identifier,
        display_name=payload.display_name,
        enabled=payload.enabled,
        is_default=payload.is_default,
        extra_params=payload.extra_params,
    )
    return to_ai_source_model_item(item)


@router.put("/sources/models", response_model=AISourceModelItem | None)
async def update_ai_source_model(
    payload: AISourceModelUpsertRequest,
    _: Annotated[Any, Depends(require_control_panel)],
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
    )
    return to_ai_source_model_item(item) if item is not None else None


@router.delete("/sources/models", response_model=bool)
async def delete_ai_source_model(
    _: Annotated[Any, Depends(require_control_panel)],
    model_id: Annotated[str, Query(min_length=1)],
    source_id: Annotated[str | None, Query(max_length=64)] = None,
) -> bool:
    return await ai_admin_service.delete_source_model(
        model_id=model_id,
        source_id=source_id,
    )


@router.get("/model-profiles", response_model=list[AIModelProfileItem])
async def list_ai_model_profiles(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelProfileItem]:
    profiles = await ai_admin_service.list_model_profiles()
    return [to_ai_model_profile_item(item) for item in profiles]


@router.put("/model-profiles", response_model=AIModelProfileItem | None)
async def upsert_ai_model_profile(
    payload: AIModelProfileUpsertRequest,
    _: Annotated[Any, Depends(require_control_panel)],
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
        )
        if payload.profile_id
        else await ai_admin_service.create_model_profile(
            name=payload.name,
            model_id=payload.model_id,
            task_class=payload.task_class,
            priority=payload.priority,
            enabled=payload.enabled,
            fallback_profile_id=payload.fallback_profile_id,
        )
    )
    return to_ai_model_profile_item(item) if item is not None else None


@router.get("/model-bindings", response_model=list[AIModelBindingItem])
async def list_ai_model_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelBindingItem]:
    bindings = await ai_admin_service.list_model_bindings()
    return [to_ai_model_binding_item(item) for item in bindings]


@router.get("/personas", response_model=list[AIPersonaItem])
async def list_ai_personas(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIPersonaItem]:
    personas = await ai_admin_service.list_personas()
    return [to_ai_persona_item(item) for item in personas]


@router.put("/personas", response_model=AIPersonaItem | None)
async def upsert_ai_persona(
    payload: AIPersonaUpsertRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIPersonaItem | None:
    persona = (
        await ai_admin_service.update_persona(
            persona_id=payload.persona_id,
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            style_prompt=payload.style_prompt,
            enabled=payload.enabled,
        )
        if payload.persona_id
        else await ai_admin_service.create_persona(
            name=payload.name,
            description=payload.description,
            system_prompt=payload.system_prompt,
            style_prompt=payload.style_prompt,
            enabled=payload.enabled,
        )
    )
    return to_ai_persona_item(persona) if persona is not None else None


@router.get("/persona-bindings", response_model=list[AIPersonaBindingItem])
async def list_ai_persona_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIPersonaBindingItem]:
    bindings = await ai_admin_service.list_persona_bindings()
    return [to_ai_persona_binding_item(item) for item in bindings]


@router.get("/memories", response_model=list[AIMemoryItem])
async def list_ai_memories(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_control_panel)],
    anchor_type: Annotated[
        Literal["scene", "participant", "user"],
        Query(),
    ],
    anchor_id: Annotated[str, Query(min_length=1)],
    query: str = "",
    memory_layer: Annotated[str | None, Query(max_length=32)] = None,
    memory_kind: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIMemoryItem]:
    memories = await ai_admin_service.list_memories(
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        query_text=query,
        memory_layer=memory_layer,
        memory_kind=memory_kind,
        limit=limit,
    )
    return [to_ai_memory_item(item) for item in memories]


@router.post("/memories", response_model=AIMemoryItem)
async def create_ai_memory(
    payload: AIMemoryCreateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIMemoryItem:
    memory = await ai_admin_service.create_memory(
        memory_layer=payload.memory_layer,
        memory_kind=payload.memory_kind,
        anchor_type=payload.anchor_type,
        anchor_id=payload.anchor_id,
        content=payload.content,
        salience=payload.salience,
        confidence=payload.confidence,
    )
    return to_ai_memory_item(memory)


@router.patch("/memories", response_model=AIMemoryItem | None)
async def update_ai_memory(
    payload: AIMemoryUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIMemoryItem | None:
    memory = await ai_admin_service.update_memory(
        memory_id=payload.memory_id,
        content=payload.content,
        salience=payload.salience,
        confidence=payload.confidence,
    )
    return to_ai_memory_item(memory) if memory is not None else None


@router.delete("/memories", response_model=AIMemoryDeleteResult)
async def delete_ai_memory(
    _: Annotated[Any, Depends(require_control_panel)],
    memory_id: Annotated[str, Query(min_length=1)],
) -> AIMemoryDeleteResult:
    return AIMemoryDeleteResult(
        deleted=await ai_admin_service.delete_memory(memory_id=memory_id)
    )


@router.get("/recent-targets", response_model=list[AIRecentTargetItem])
async def list_ai_recent_targets(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRecentTargetItem]:
    targets = await ai_admin_service.list_recent_targets(limit=limit)
    return [to_ai_recent_target_item(item) for item in targets]


@router.get("/conversations", response_model=list[AIConversationItem])
async def list_ai_conversations(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIConversationItem]:
    conversations = await ai_admin_service.list_recent_conversations(limit=limit)
    return [to_ai_conversation_item(item) for item in conversations]


@router.get("/conversations/turns", response_model=list[AIConversationTurnItem])
async def list_ai_conversation_turns(
    _: Annotated[Any, Depends(require_control_panel)],
    conversation_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIConversationTurnItem]:
    turns = await ai_admin_service.list_conversation_turns(
        conversation_id=conversation_id,
        limit=limit,
    )
    return [to_ai_conversation_turn_item(item) for item in turns]


@router.get(
    "/conversations/prompt-preview",
    response_model=AIConversationPromptPreviewItem | None,
)
async def get_ai_conversation_prompt_preview(
    _: Annotated[Any, Depends(require_control_panel)],
    conversation_id: Annotated[str, Query(min_length=1)],
    turn_limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AIConversationPromptPreviewItem | None:
    preview = await ai_admin_service.build_prompt_preview(
        conversation_id=conversation_id,
        turn_limit=turn_limit,
    )
    if preview is None:
        return None
    return to_ai_conversation_prompt_preview_item(preview)


@router.get("/future-tasks", response_model=list[AIFutureTaskItem])
async def list_ai_future_tasks(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIFutureTaskItem]:
    tasks = await ai_admin_service.list_future_tasks(limit=limit)
    return [to_ai_future_task_item(item) for item in tasks]


@router.delete("/future-tasks", response_model=AIFutureTaskItem | None)
async def cancel_ai_future_task(
    _: Annotated[Any, Depends(require_control_panel)],
    task_id: Annotated[str, Query(min_length=1)],
) -> AIFutureTaskItem | None:
    task = await ai_admin_service.cancel_future_task(task_id=task_id)
    if task is None:
        return None
    return to_ai_future_task_item(task)


@router.get("/relationships/list", response_model=list[AIRelationshipStateItem])
async def list_ai_relationships(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIRelationshipStateItem]:
    states = await ai_admin_service.list_relationships(limit=limit)
    return [to_ai_relationship_state_item(state) for state in states]


@router.get("/relationships", response_model=AIRelationshipStateItem)
async def get_ai_relationship_state(
    _: Annotated[Any, Depends(require_control_panel)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
    group_id: Annotated[str | None, Query()] = None,
) -> AIRelationshipStateItem:
    state = await ai_admin_service.get_relationship_state(
        platform=platform,
        group_id=group_id,
        user_id=user_id,
    )
    return to_ai_relationship_state_item(state)


@router.patch("/relationships", response_model=AIRelationshipStateItem)
async def update_ai_relationship_score(
    payload: AIRelationshipScoreUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIRelationshipStateItem:
    state = await ai_admin_service.set_relationship_score(
        platform=payload.platform,
        group_id=payload.group_id,
        user_id=payload.user_id,
        score=payload.score,
    )
    return to_ai_relationship_state_item(state)


@router.get("/tools", response_model=list[AIToolItem])
async def list_ai_tools(
    _: Annotated[Any, Depends(require_control_panel)],
    *,
    allowed_only: Annotated[bool, Query()] = False,
) -> list[AIToolItem]:
    policy = (
        AIToolPolicy(
            allow_high_risk_tools=False,
            allow_capability_bridge=False,
        )
        if allowed_only
        else None
    )
    tools = ai_admin_service.list_tools(policy=policy)
    return [to_ai_tool_item(item) for item in tools]


@router.get("/skills", response_model=list[AISkillItem])
async def list_ai_skills(
    _: Annotated[Any, Depends(require_control_panel)],
    *,
    allowed_only: Annotated[bool, Query()] = False,
) -> list[AISkillItem]:
    """List product-facing AI skills."""

    policy = (
        AIToolPolicy(
            allow_high_risk_tools=False,
            allow_capability_bridge=False,
        )
        if allowed_only
        else None
    )
    skills = ai_admin_service.list_skills(policy=policy)
    return [to_ai_skill_item(item) for item in skills]


@router.post("/tools/policy-preview", response_model=AIToolPolicyPreviewItem)
async def preview_ai_tool_policy(
    payload: AIToolPolicyPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIToolPolicyPreviewItem:
    policy = ai_admin_service.preview_tool_policy(
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return to_ai_tool_policy_preview_item(policy)


@router.post("/tools/intent-preview", response_model=list[AIToolIntentPreviewItem])
async def preview_ai_tool_intents(
    payload: AIToolIntentPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIToolIntentPreviewItem]:
    intents = await ai_admin_service.preview_tool_intents(
        message_text=payload.message_text,
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return [to_ai_tool_intent_preview_item(item) for item in intents]


@router.post("/debug/skills/policy-preview", response_model=AIToolPolicyPreviewItem)
async def preview_ai_skill_policy_debug(
    payload: AIToolPolicyPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIToolPolicyPreviewItem:
    """Advanced debug alias retained during the boundary-freeze phase."""

    policy = ai_admin_service.preview_tool_policy(
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return to_ai_tool_policy_preview_item(policy)


@router.get("/tools/policy-bindings", response_model=list[AIToolPolicyBindingItem])
async def list_ai_tool_policy_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIToolPolicyBindingItem]:
    rows = await ai_admin_service.list_tool_policy_bindings()
    return [to_ai_tool_policy_binding_item(item) for item in rows]


@router.post("/tools/policy-bindings", response_model=AIToolPolicyBindingItem)
async def create_ai_tool_policy_binding(
    payload: AIToolPolicyBindingCreateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIToolPolicyBindingItem:
    item = await ai_admin_service.create_tool_policy_binding(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return to_ai_tool_policy_binding_item(item)


@router.patch("/tools/policy-bindings", response_model=AIToolPolicyBindingItem | None)
async def update_ai_tool_policy_binding(
    payload: AIToolPolicyBindingUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIToolPolicyBindingItem | None:
    item = await ai_admin_service.update_tool_policy_binding(
        binding_id=payload.binding_id,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    if item is None:
        return None
    return to_ai_tool_policy_binding_item(item)


@router.delete("/tools/policy-bindings")
async def delete_ai_tool_policy_binding(
    _: Annotated[Any, Depends(require_control_panel)],
    binding_id: Annotated[str, Query(min_length=1)],
) -> dict[str, bool]:
    deleted = await ai_admin_service.delete_tool_policy_binding(
        binding_id=binding_id,
    )
    return {"deleted": deleted}


@router.post("/tools/capability-preview", response_model=AICapabilityPreviewItem)
async def preview_ai_capability(
    payload: AICapabilityPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AICapabilityPreviewItem:
    preview = ai_admin_service.preview_capability(
        capability_name=payload.capability_name,
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return to_ai_capability_preview_item(preview)


@router.post("/debug/skills/capability-preview", response_model=AICapabilityPreviewItem)
async def preview_ai_skill_capability_debug(
    payload: AICapabilityPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AICapabilityPreviewItem:
    """Advanced debug alias retained during the boundary-freeze phase."""

    preview = ai_admin_service.preview_capability(
        capability_name=payload.capability_name,
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
    )
    return to_ai_capability_preview_item(preview)


@router.get("/tools/capabilities", response_model=list[AICapabilityItem])
async def list_ai_capabilities(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AICapabilityItem]:
    rows = ai_admin_service.list_capabilities()
    return [to_ai_capability_item(item) for item in rows]


@router.get("/tools/executions", response_model=list[AIToolExecutionItem])
async def list_ai_tool_executions(
    _: Annotated[Any, Depends(require_control_panel)],
    conversation_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    rows = await ai_admin_service.list_tool_executions(
        conversation_id=conversation_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]


@router.get("/debug/skills/executions", response_model=list[AIToolExecutionItem])
async def list_ai_skill_executions_debug(
    _: Annotated[Any, Depends(require_control_panel)],
    conversation_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    """Advanced debug alias retained during the boundary-freeze phase."""

    rows = await ai_admin_service.list_tool_executions(
        conversation_id=conversation_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]
