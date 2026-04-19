"""AI session / scene / prompt-preview admin routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai.admin.service import ai_admin_service
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import (
    to_ai_chat_message_item,
    to_ai_recent_target_item,
    to_ai_session_item,
    to_ai_session_prompt_preview_item,
)
from apeiria.interfaces.http.schemas.ai_models import (
    AIChatMessageItem,
    AIRecentTargetItem,
    AISessionItem,
    AISessionPromptPreviewItem,
)

router = APIRouter()


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


__all__ = ["router"]
