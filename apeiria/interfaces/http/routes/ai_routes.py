"""AI admin routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai.admin.service import ai_admin_service
from apeiria.app.ai.tools.models import AIToolPolicy
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import (
    to_ai_capability_item,
    to_ai_capability_preview_item,
    to_ai_conversation_item,
    to_ai_conversation_prompt_preview_item,
    to_ai_conversation_turn_item,
    to_ai_memory_item,
    to_ai_model_binding_item,
    to_ai_model_profile_item,
    to_ai_persona_binding_item,
    to_ai_persona_item,
    to_ai_provider_item,
    to_ai_provider_model_item,
    to_ai_relationship_state_item,
    to_ai_skill_item,
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
    AIMemoryItem,
    AIModelBindingItem,
    AIModelProfileItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIProviderItem,
    AIProviderModelItem,
    AIProviderModelListRequest,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
    AISkillItem,
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


@router.get("/providers", response_model=list[AIProviderItem])
async def list_ai_providers(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIProviderItem]:
    providers = await ai_admin_service.list_providers()
    return [to_ai_provider_item(item) for item in providers]


@router.post("/providers/models", response_model=list[AIProviderModelItem])
async def list_ai_provider_models(
    payload: AIProviderModelListRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIProviderModelItem]:
    rows = await ai_admin_service.list_provider_models(
        provider_id=payload.provider_id,
        api_key=payload.api_key,
    )
    return [to_ai_provider_model_item(item) for item in rows]


@router.get("/model-profiles", response_model=list[AIModelProfileItem])
async def list_ai_model_profiles(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIModelProfileItem]:
    profiles = await ai_admin_service.list_model_profiles()
    return [to_ai_model_profile_item(item) for item in profiles]


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


@router.get("/persona-bindings", response_model=list[AIPersonaBindingItem])
async def list_ai_persona_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIPersonaBindingItem]:
    bindings = await ai_admin_service.list_persona_bindings()
    return [to_ai_persona_binding_item(item) for item in bindings]


@router.get("/memories", response_model=list[AIMemoryItem])
async def list_ai_memories(
    _: Annotated[Any, Depends(require_control_panel)],
    subject_type: Annotated[str, Query(min_length=1)],
    subject_id: Annotated[str, Query(min_length=1)],
    query: str = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIMemoryItem]:
    memories = await ai_admin_service.list_memories(
        subject_type=subject_type,
        subject_id=subject_id,
        query_text=query,
        limit=limit,
    )
    return [to_ai_memory_item(item) for item in memories]


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
    intents = ai_admin_service.preview_tool_intents(
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
