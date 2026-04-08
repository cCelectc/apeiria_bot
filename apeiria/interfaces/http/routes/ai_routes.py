"""AI admin routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai.admin_service import ai_admin_service
from apeiria.app.ai.tools.models import AIToolPolicy
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import (
    to_ai_memory_item,
    to_ai_persona_binding_item,
    to_ai_persona_item,
    to_ai_relationship_state_item,
    to_ai_tool_execution_item,
    to_ai_tool_item,
)
from apeiria.interfaces.http.schemas.ai_models import (
    AIMemoryItem,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
    AIToolExecutionItem,
    AIToolItem,
)

router = APIRouter()


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


@router.get("/tools/executions", response_model=list[AIToolExecutionItem])
async def list_ai_tool_executions(
    _: Annotated[Any, Depends(require_control_panel)],
    conversation_id: Annotated[str, Query(min_length=1)],
) -> list[AIToolExecutionItem]:
    rows = await ai_admin_service.list_tool_executions(
        conversation_id=conversation_id,
    )
    return [to_ai_tool_execution_item(item) for item in rows]
