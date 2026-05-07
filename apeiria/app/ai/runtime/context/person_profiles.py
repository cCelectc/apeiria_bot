"""Runtime person profile prompt steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.person import ai_person_profile_service

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryExtractionCandidate
    from apeiria.conversation.models import ChatSessionIdentity


async def load_person_profile_for_prompt(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
) -> tuple[str, ...]:
    """Load prompt-ready person profile lines for the active user."""

    profile = await ai_person_profile_service.build_prompt_profile(
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
    )
    if profile is None:
        return ()
    return profile.prompt_lines


async def ingest_person_profile_from_memory(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    source_message_id: str | None,
    candidates: tuple["AIMemoryExtractionCandidate", ...],
    self_introduction_name: str | None,
) -> None:
    await ai_person_profile_service.ingest_message(
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        source_message_id=source_message_id,
        candidates=candidates,
        self_introduction_name=self_introduction_name,
    )
