"""AI session query and prompt-preview application entry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatMessageDetailView, ChatSessionAdminView

    from .models import AIRecentTarget, AISessionPromptPreview


@dataclass(frozen=True, slots=True)
class AISessionsService:
    """Read-side AI session browsing and prompt-preview operations."""

    async def list_recent_sessions(
        self,
        *,
        limit: int = 20,
    ) -> list["ChatSessionAdminView"]:
        from . import scenes

        return await scenes.list_recent_sessions(limit=limit)

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list["AIRecentTarget"]:
        from . import targets

        return await targets.list_recent_targets(limit=limit)

    async def list_scene_turns(
        self,
        *,
        scene_id: str,
        limit: int = 50,
    ) -> list["ChatMessageDetailView"]:
        from . import scenes

        return await scenes.list_scene_turns(scene_id=scene_id, limit=limit)

    async def build_scene_prompt_preview(
        self,
        *,
        scene_id: str,
        turn_limit: int = 50,
    ) -> "AISessionPromptPreview | None":
        from . import prompt_preview

        return await prompt_preview.build_scene_prompt_preview(
            scene_id=scene_id,
            turn_limit=turn_limit,
        )


@dataclass(frozen=True, slots=True)
class AISessionsEntry:
    """Application entry for AI session read-side behavior."""

    service: AISessionsService = field(default_factory=AISessionsService)

    async def list_recent_sessions(
        self,
        *,
        limit: int = 20,
    ) -> list["ChatSessionAdminView"]:
        """List recent AI-backed chat sessions."""

        return await self.service.list_recent_sessions(limit=limit)

    async def list_recent_targets(
        self,
        *,
        limit: int = 20,
    ) -> list["AIRecentTarget"]:
        """List recent scene/user/participant targets for AI state browsing."""

        return await self.service.list_recent_targets(limit=limit)

    async def list_scene_turns(
        self,
        *,
        scene_id: str,
        limit: int = 50,
    ) -> list["ChatMessageDetailView"]:
        """List recent turns for one AI session scene."""

        return await self.service.list_scene_turns(scene_id=scene_id, limit=limit)

    async def build_scene_prompt_preview(
        self,
        *,
        scene_id: str,
        turn_limit: int = 50,
    ) -> "AISessionPromptPreview | None":
        """Build a non-mutating prompt preview for one AI session scene."""

        return await self.service.build_scene_prompt_preview(
            scene_id=scene_id,
            turn_limit=turn_limit,
        )


ai_sessions_service = AISessionsService()

__all__ = ["AISessionsEntry", "AISessionsService", "ai_sessions_service"]
