"""AI tools / skills / capabilities / policy-bindings / executions routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.tools import AIToolPolicy, coerce_tool_level
from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .tools_schemas import (
    AICapabilityItem,
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
    to_ai_capability_item,
    to_ai_skill_item,
    to_ai_tool_execution_item,
    to_ai_tool_intent_preview_item,
    to_ai_tool_item,
    to_ai_tool_policy_binding_item,
    to_ai_tool_policy_preview_item,
)

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
    policy = AIToolPolicy() if allowed_only else None
    tools = ai_application.operations.list_tools(policy=policy)
    return [to_ai_tool_item(item) for item in tools]


@router.get("/skills", response_model=list[AISkillItem])
async def list_ai_skills(
    _: Annotated[Any, Depends(require_control_panel)],
    *,
    allowed_only: Annotated[bool, Query()] = False,
) -> list[AISkillItem]:
    """List product-facing AI skills."""

    policy = AIToolPolicy() if allowed_only else None
    skills = ai_application.operations.list_skills(policy=policy)
    return [to_ai_skill_item(item) for item in skills]


@router.post("/tools/policy-preview", response_model=AIToolPolicyPreviewItem)
async def preview_ai_tool_policy(
    payload: AIToolPolicyPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIToolPolicyPreviewItem:
    policy = ai_application.operations.preview_tool_policy(
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allowed_level=payload.allowed_level,
    )
    return to_ai_tool_policy_preview_item(policy)


@router.post("/tools/intent-preview", response_model=list[AIToolIntentPreviewItem])
async def preview_ai_tool_intents(
    payload: AIToolIntentPreviewRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIToolIntentPreviewItem]:
    intents = await ai_application.operations.preview_tool_intents(
        message_text=payload.message_text,
        scope_type=payload.scope_type,
        is_tome=payload.is_tome,
        allowed_level=coerce_tool_level(payload.allowed_level),
    )
    return [to_ai_tool_intent_preview_item(item) for item in intents]


@router.get("/tools/policy-bindings", response_model=list[AIToolPolicyBindingItem])
async def list_ai_tool_policy_bindings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AIToolPolicyBindingItem]:
    rows = await ai_application.operations.list_tool_policy_bindings()
    return [to_ai_tool_policy_binding_item(item) for item in rows]


@router.post("/tools/policy-bindings", response_model=AIToolPolicyBindingItem)
async def create_ai_tool_policy_binding(
    payload: AIToolPolicyBindingCreateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIToolPolicyBindingItem:
    item = await ai_application.operations.create_tool_policy_binding(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        allowed_level=coerce_tool_level(payload.allowed_level),
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_tool_policy_binding_item(item)


@router.patch("/tools/policy-bindings", response_model=AIToolPolicyBindingItem | None)
async def update_ai_tool_policy_binding(
    payload: AIToolPolicyBindingUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIToolPolicyBindingItem | None:
    item = await ai_application.operations.update_tool_policy_binding(
        binding_id=payload.binding_id,
        allowed_level=coerce_tool_level(payload.allowed_level),
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
    deleted = await ai_application.operations.delete_tool_policy_binding(
        binding_id=binding_id,
        actor_username=_actor_username_from_claims(session),
    )
    return {"deleted": deleted}


@router.get("/tools/capabilities", response_model=list[AICapabilityItem])
async def list_ai_capabilities(
    _: Annotated[Any, Depends(require_control_panel)],
) -> list[AICapabilityItem]:
    rows = ai_application.operations.list_capabilities()
    return [to_ai_capability_item(item) for item in rows]


@router.get("/tools/executions", response_model=list[AIToolExecutionItem])
async def list_ai_tool_executions(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    rows = await ai_application.operations.list_tool_executions(
        session_id=scene_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]


__all__ = ["router"]
