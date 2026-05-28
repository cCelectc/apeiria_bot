"""Runtime profile prompt steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.profile import AIProfileCard
    from apeiria.conversation.models import ChatSessionIdentity


async def load_profile_card_for_context(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    memories: tuple["AIMemoryDefinition", ...] = (),
) -> "AIProfileCard | None":
    """Load runtime profile-card projection for the active user."""

    return await ai_wiring.profile_service.build_profile_card(
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        scene_type=identity.scene_type,
        memories=memories,
    )


async def ingest_profile_from_message(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    self_introduction_name: str | None,
) -> None:
    await ai_wiring.profile_service.ingest_message(
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        scene_type=identity.scene_type,
        self_introduction_name=self_introduction_name,
    )
