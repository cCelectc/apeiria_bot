"""AI relationship admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.ai.admin.runtime_service import ai_runtime_admin_service
from apeiria.ai.webui.schemas import (
    AIRelationshipEventItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
)
from apeiria.ai.webui.support import (
    to_ai_relationship_event_item,
    to_ai_relationship_state_item,
)
from apeiria.webui.auth import require_control_panel

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/relationships/list", response_model=list[AIRelationshipStateItem])
async def list_ai_relationships(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIRelationshipStateItem]:
    states = await ai_runtime_admin_service.list_relationships(limit=limit)
    return [to_ai_relationship_state_item(state) for state in states]


@router.get("/relationships", response_model=AIRelationshipStateItem)
async def get_ai_relationship_state(
    _: Annotated[Any, Depends(require_control_panel)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
    group_id: Annotated[str | None, Query()] = None,
) -> AIRelationshipStateItem:
    state = await ai_runtime_admin_service.get_relationship_state(
        platform=platform,
        group_id=group_id,
        user_id=user_id,
    )
    return to_ai_relationship_state_item(state)


@router.get("/relationships/events", response_model=list[AIRelationshipEventItem])
async def list_ai_relationship_events(
    _: Annotated[Any, Depends(require_control_panel)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
    group_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRelationshipEventItem]:
    events = await ai_runtime_admin_service.list_relationship_events(
        platform=platform,
        group_id=group_id,
        user_id=user_id,
        limit=limit,
    )
    return [to_ai_relationship_event_item(item) for item in events]


@router.patch("/relationships", response_model=AIRelationshipStateItem)
async def update_ai_relationship_score(
    payload: AIRelationshipScoreUpdateRequest,
    session: Annotated["AuthSession", Depends(require_control_panel)],
) -> AIRelationshipStateItem:
    state = await ai_runtime_admin_service.set_relationship_score(
        platform=payload.platform,
        group_id=payload.group_id,
        user_id=payload.user_id,
        score=payload.score,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_relationship_state_item(state)


__all__ = ["router"]
