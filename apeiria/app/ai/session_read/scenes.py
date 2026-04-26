"""Scene/session reads backed by the neutral conversation core."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatMessageDetailView, ChatSessionAdminView


async def list_recent_sessions(
    *,
    limit: int = 20,
) -> list["ChatSessionAdminView"]:
    return await chat_session_service.list_recent_sessions(limit=limit)


async def list_scene_turns(
    *,
    scene_id: str,
    limit: int = 50,
) -> list["ChatMessageDetailView"]:
    return await chat_session_service.list_messages_for_session(
        session_id=scene_id,
        limit=limit,
    )
