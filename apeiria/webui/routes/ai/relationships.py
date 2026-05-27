"""AI relationship admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .relationships_schemas import (
    AIRelationshipEventItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
    to_ai_relationship_event_item,
    to_ai_relationship_state_item,
)

if TYPE_CHECKING:
    from apeiria.access.principal import AuthSession


router = APIRouter()


def _actor_username_from_claims(session: "AuthSession") -> str | None:
    username = session.username.strip()
    return username or None


@router.get("/relationships/list", response_model=list[AIRelationshipStateItem])
async def list_ai_relationships(
    _: Annotated[Any, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIRelationshipStateItem]:
    states = await ai_application.operations.list_relationships(limit=limit)
    return [to_ai_relationship_state_item(state) for state in states]


@router.get("/relationships", response_model=AIRelationshipStateItem)
async def get_ai_relationship_state(
    _: Annotated[Any, Depends(require_auth)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
) -> AIRelationshipStateItem:
    state = await ai_application.operations.get_relationship_state(
        platform=platform,
        user_id=user_id,
    )
    return to_ai_relationship_state_item(state)


@router.get("/relationships/events", response_model=list[AIRelationshipEventItem])
async def list_ai_relationship_events(
    _: Annotated[Any, Depends(require_auth)],
    platform: Annotated[str, Query(min_length=1)],
    user_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRelationshipEventItem]:
    events = await ai_application.operations.list_relationship_events(
        platform=platform,
        user_id=user_id,
        limit=limit,
    )
    return [to_ai_relationship_event_item(item) for item in events]


@router.patch("/relationships", response_model=AIRelationshipStateItem)
async def update_ai_relationship_score(
    payload: AIRelationshipScoreUpdateRequest,
    session: Annotated["AuthSession", Depends(require_auth)],
) -> AIRelationshipStateItem:
    state = await ai_application.operations.set_relationship_score(
        platform=payload.platform,
        user_id=payload.user_id,
        score=payload.score,
        scene_id=payload.scene_id,
        actor_username=_actor_username_from_claims(session),
    )
    return to_ai_relationship_state_item(state)


__all__ = ["router"]
