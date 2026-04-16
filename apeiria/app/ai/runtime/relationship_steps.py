"""Runtime relationship steps extracted from the orchestration compatibility layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.relationship.scoring import project_emotion
from apeiria.app.ai.relationship.service import ai_relationship_service
from apeiria.app.ai.relationship.signals import derive_relationship_delta

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ChatSessionIdentity
    from apeiria.app.ai.relationship.models import AIRelationshipState


@dataclass(frozen=True)
class AIRelationshipTarget:
    """Resolved relationship target for one runtime turn."""

    platform: str
    group_id: str | None
    user_id: str
    is_private: bool


def build_relationship_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIRelationshipTarget:
    """Build one relationship target from the current conversation identity."""

    return AIRelationshipTarget(
        platform=identity.platform,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
        user_id=identity.subject_id or user_id,
        is_private=identity.scene_type == "private",
    )


def format_relationship_context(
    state: "AIRelationshipState",
) -> str | None:
    """Render relationship state into one prompt-side context string."""

    projection = project_emotion(state)
    mood_tags = ", ".join(state.mood_tags) if state.mood_tags else "none"
    return "\n".join(
        (
            f"Affinity score: {state.score:.2f}",
            f"Projected tone: {projection.tone}",
            f"Warmth bias: {projection.warmth_bias:.2f}",
            f"Initiative bias: {projection.initiative_bias:.2f}",
            f"Recent mood tags: {mood_tags}",
        )
    )


async def load_relationship_context(
    session: "AsyncSession",
    *,
    target: AIRelationshipTarget,
) -> str | None:
    """Load prompt-ready relationship context for the current target."""

    state = await ai_relationship_service.get_state(
        session,
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
    )
    return format_relationship_context(state)


async def update_relationship_state(
    session: "AsyncSession",
    *,
    target: AIRelationshipTarget,
    message_text: str,
    is_tome: bool,
) -> None:
    """Apply relationship deltas derived from the current inbound message."""

    delta = derive_relationship_delta(
        text=message_text,
        is_private=target.is_private,
        is_tome=is_tome,
    )
    if delta is None:
        return

    await ai_relationship_service.apply_delta(
        session,
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
        delta=delta,
    )
