"""AI session / scene / prompt-preview admin routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_control_panel

from .sessions_schemas import (
    AIChatMessageItem,
    AIManagedSessionAIEnabledUpdate,
    AIManagedSessionDetailItem,
    AIManagedSessionItem,
    AIManagedSessionPersonaUpdate,
    AIRecentTargetItem,
    AISessionItem,
    AISessionPromptPreviewItem,
    to_ai_chat_message_item,
    to_ai_managed_session_detail_item,
    to_ai_managed_session_item,
    to_ai_recent_target_item,
    to_ai_session_item,
    to_ai_session_prompt_preview_item,
)

router = APIRouter()


@router.get("/recent-targets", response_model=list[AIRecentTargetItem])
async def list_ai_recent_targets(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRecentTargetItem]:
    targets = await ai_application.sessions.list_recent_targets(limit=limit)
    return [to_ai_recent_target_item(item) for item in targets]


@router.get("/scenes", response_model=list[AISessionItem])
async def list_ai_scenes(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AISessionItem]:
    conversations = await ai_application.sessions.list_recent_sessions(limit=limit)
    return [to_ai_session_item(item) for item in conversations]


@router.get("/scenes/turns", response_model=list[AIChatMessageItem])
async def list_ai_scene_turns(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIChatMessageItem]:
    turns = await ai_application.sessions.list_scene_turns(
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
    preview = await ai_application.sessions.build_scene_prompt_preview(
        scene_id=scene_id,
        turn_limit=turn_limit,
    )
    if preview is None:
        return None
    return to_ai_session_prompt_preview_item(preview)


@router.get("/managed-sessions", response_model=list[AIManagedSessionItem])
async def list_ai_managed_sessions(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AIManagedSessionItem]:
    sessions = await ai_application.sessions.list_managed_sessions(limit=limit)
    return [to_ai_managed_session_item(item) for item in sessions]


@router.get(
    "/managed-sessions/{session_id:path}",
    response_model=AIManagedSessionDetailItem,
)
async def get_ai_managed_session(
    _: Annotated[Any, Depends(require_control_panel)],
    session_id: str,
    message_limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AIManagedSessionDetailItem:
    detail = await ai_application.sessions.get_managed_session_detail(
        session_id=session_id,
        message_limit=message_limit,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="managed_session_not_found",
        )
    return to_ai_managed_session_detail_item(detail)


@router.patch(
    "/managed-sessions/{session_id:path}/ai-enabled",
    response_model=AIManagedSessionDetailItem,
)
async def update_ai_managed_session_enabled(
    session: Annotated[Any, Depends(require_control_panel)],
    session_id: str,
    payload: AIManagedSessionAIEnabledUpdate,
) -> AIManagedSessionDetailItem:
    detail = await ai_application.sessions.set_managed_session_ai_enabled(
        session_id=session_id,
        ai_enabled=payload.ai_enabled,
        actor_id=_session_actor_id(session),
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="managed_session_not_found",
        )
    return to_ai_managed_session_detail_item(detail)


@router.patch(
    "/managed-sessions/{session_id:path}/persona",
    response_model=AIManagedSessionDetailItem,
)
async def update_ai_managed_session_persona(
    session: Annotated[Any, Depends(require_control_panel)],
    session_id: str,
    payload: AIManagedSessionPersonaUpdate,
) -> AIManagedSessionDetailItem:
    detail = await ai_application.sessions.set_managed_session_persona(
        session_id=session_id,
        persona_id=payload.persona_id,
        actor_id=_session_actor_id(session),
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="managed_session_not_found",
        )
    return to_ai_managed_session_detail_item(detail)


@router.post(
    "/managed-sessions/{session_id:path}/context-reset",
    response_model=AIManagedSessionDetailItem,
)
async def reset_ai_managed_session_context(
    session: Annotated[Any, Depends(require_control_panel)],
    session_id: str,
) -> AIManagedSessionDetailItem:
    detail = await ai_application.sessions.reset_managed_session_context(
        session_id=session_id,
        actor_id=_session_actor_id(session),
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="managed_session_not_found",
        )
    return to_ai_managed_session_detail_item(detail)


def _session_actor_id(session: Any) -> str | None:
    value = getattr(session, "user_id", None)
    return value if isinstance(value, str) else None


__all__ = ["router"]
