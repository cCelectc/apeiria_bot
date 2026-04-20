"""AI tools / skills / capabilities / policy-bindings / executions routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.admin.service import ai_admin_service
from apeiria.ai.tools.models import AIToolPolicy
from apeiria.ai.webui.schemas import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AICapabilityPreviewRequest,
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
from apeiria.ai.webui.support import (
    to_ai_capability_item,
    to_ai_capability_preview_item,
    to_ai_skill_item,
    to_ai_tool_execution_item,
    to_ai_tool_intent_preview_item,
    to_ai_tool_item,
    to_ai_tool_policy_binding_item,
    to_ai_tool_policy_preview_item,
)
from apeiria.webui.auth import require_control_panel

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


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
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIToolPolicyBindingItem:
    item = await ai_admin_service.create_tool_policy_binding(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_tool_policy_binding_item(item)


@router.patch("/tools/policy-bindings", response_model=AIToolPolicyBindingItem | None)
async def update_ai_tool_policy_binding(
    payload: AIToolPolicyBindingUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIToolPolicyBindingItem | None:
    item = await ai_admin_service.update_tool_policy_binding(
        binding_id=payload.binding_id,
        allow_read_only_tools=payload.allow_read_only_tools,
        capability_mode=payload.capability_mode,
        actor_username=_actor_username_from_claims(session),
    )
    if item is None:
        return None
    return to_ai_tool_policy_binding_item(item)


@router.delete("/tools/policy-bindings")
async def delete_ai_tool_policy_binding(
    session: Annotated["AuthSession", Depends(require_control_panel)],
    binding_id: Annotated[str, Query(min_length=1)],
) -> dict[str, bool]:
    deleted = await ai_admin_service.delete_tool_policy_binding(
        binding_id=binding_id,
        actor_username=_actor_username_from_claims(session),
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
    scene_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    rows = await ai_admin_service.list_tool_executions(
        session_id=scene_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]


@router.get("/debug/skills/executions", response_model=list[AIToolExecutionItem])
async def list_ai_skill_executions_debug(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    """Advanced debug alias retained during the boundary-freeze phase."""

    rows = await ai_admin_service.list_tool_executions(
        session_id=scene_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]


__all__ = ["router"]
