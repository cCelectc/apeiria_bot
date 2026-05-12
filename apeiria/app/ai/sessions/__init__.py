"""AI session query and prompt-preview application entry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.sessions.models import (
        AIRecentTarget,
        AISessionDetail,
        AISessionInventoryItem,
        AISessionPromptPreview,
    )
    from apeiria.conversation.models import ChatMessageDetailView, ChatSessionAdminView


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

    async def list_managed_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list["AISessionInventoryItem"]:
        from .management import AISessionManagementReader

        return await AISessionManagementReader().list_sessions(limit=limit)

    async def get_managed_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> "AISessionDetail | None":
        from .management import AISessionManagementReader

        return await AISessionManagementReader().get_session_detail(
            session_id=session_id,
            message_limit=message_limit,
        )

    async def set_managed_session_ai_enabled(
        self,
        *,
        session_id: str,
        ai_enabled: bool,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        from .models import AISessionManagementUpdate
        from .repository import AISessionManagementRepository

        repository = AISessionManagementRepository()
        updated = await repository.update_session(
            session_id=session_id,
            update=AISessionManagementUpdate(
                ai_enabled=ai_enabled,
                actor_id=actor_id,
            ),
        )
        if updated is None:
            return None
        return await self.get_managed_session_detail(session_id=session_id)

    async def set_managed_session_persona(
        self,
        *,
        session_id: str,
        persona_id: str | None,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        from .models import AISessionManagementUpdate
        from .repository import AISessionManagementRepository

        repository = AISessionManagementRepository()
        updated = await repository.update_session(
            session_id=session_id,
            update=AISessionManagementUpdate(
                persona_id=persona_id,
                actor_id=actor_id,
            ),
        )
        if updated is None:
            return None
        return await self.get_managed_session_detail(session_id=session_id)

    async def reset_managed_session_context(
        self,
        *,
        session_id: str,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        from .repository import AISessionManagementRepository

        repository = AISessionManagementRepository()
        updated = await repository.mark_context_reset(
            session_id=session_id,
            actor_id=actor_id,
        )
        if updated is None:
            return None
        return await self.get_managed_session_detail(session_id=session_id)


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

    async def list_managed_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list["AISessionInventoryItem"]:
        """List managed AI session inventory rows."""

        return await self.service.list_managed_sessions(limit=limit)

    async def get_managed_session_detail(
        self,
        *,
        session_id: str,
        message_limit: int = 50,
    ) -> "AISessionDetail | None":
        """Read one managed AI session detail."""

        return await self.service.get_managed_session_detail(
            session_id=session_id,
            message_limit=message_limit,
        )

    async def set_managed_session_ai_enabled(
        self,
        *,
        session_id: str,
        ai_enabled: bool,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        """Toggle AI reply generation for one managed session."""

        return await self.service.set_managed_session_ai_enabled(
            session_id=session_id,
            ai_enabled=ai_enabled,
            actor_id=actor_id,
        )

    async def set_managed_session_persona(
        self,
        *,
        session_id: str,
        persona_id: str | None,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        """Assign or clear one session persona override."""

        return await self.service.set_managed_session_persona(
            session_id=session_id,
            persona_id=persona_id,
            actor_id=actor_id,
        )

    async def reset_managed_session_context(
        self,
        *,
        session_id: str,
        actor_id: str | None = None,
    ) -> "AISessionDetail | None":
        """Set a context reset marker for one managed session."""

        return await self.service.reset_managed_session_context(
            session_id=session_id,
            actor_id=actor_id,
        )


ai_sessions_service = AISessionsService()

__all__ = ["AISessionsEntry", "AISessionsService", "ai_sessions_service"]
