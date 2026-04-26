"""Facade for AI session read operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import prompt_preview, scenes, targets

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatMessageDetailView, ChatSessionAdminView

    from .models import AIRecentTarget, AISessionPromptPreview


class AISessionReadService:
    """Read-side AI session browsing and workbench preview operations."""

    async def list_recent_sessions(
        self,
        *,
        limit: int = 20,
    ) -> list["ChatSessionAdminView"]:
        return await scenes.list_recent_sessions(limit=limit)

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list["AIRecentTarget"]:
        return await targets.list_recent_targets(limit=limit)

    async def list_scene_turns(
        self,
        *,
        scene_id: str,
        limit: int = 50,
    ) -> list["ChatMessageDetailView"]:
        return await scenes.list_scene_turns(scene_id=scene_id, limit=limit)

    async def build_scene_prompt_preview(
        self,
        *,
        scene_id: str,
        turn_limit: int = 50,
    ) -> "AISessionPromptPreview | None":
        return await prompt_preview.build_scene_prompt_preview(
            scene_id=scene_id,
            turn_limit=turn_limit,
        )


ai_session_read_service = AISessionReadService()

__all__ = ["AISessionReadService", "ai_session_read_service"]
