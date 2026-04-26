"""Runtime relationship steps extracted from the orchestration compatibility layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.relationship import (
    TONE_LABEL,
    ai_relationship_service,
    derive_relationship_delta,
    project_emotion,
)

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.ai.relationship import AIRelationshipEvent, AIRelationshipState
    from apeiria.conversation.models import ChatSessionIdentity


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
    *,
    recent_events: tuple["AIRelationshipEvent", ...] = (),
) -> str | None:
    """Render relationship state into prompt-facing behavioral guidance."""

    projection = project_emotion(state)
    tone_label = TONE_LABEL.get(projection.tone, projection.tone)
    sections = [
        "⚠ 关系调制仅影响表达层（语气、措辞、主动性），不改变人格核心设定。",
        f"当前关系: {tone_label} (score={state.score:.2f})",
    ]
    if projection.style_modulation:
        sections.append("表达调制:")
        sections.extend(f"- {line}" for line in projection.style_modulation)
    if state.mood_tags:
        sections.append(f"近期互动氛围: {', '.join(state.mood_tags)}")
    if recent_events:
        sections.append("近期关系事件:")
        sections.extend(
            _format_relationship_event_line(event) for event in recent_events
        )
    return "\n".join(sections)


async def load_relationship_context(
    *,
    target: AIRelationshipTarget,
) -> str | None:
    """Load prompt-ready relationship context for the current target."""

    state = await ai_relationship_service.get_state(
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
    )
    effective_state = await ai_relationship_service.get_effective_state(
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
    )
    events = await ai_relationship_service.list_events(
        affinity_id=state.affinity_id,
        limit=3,
    )
    return format_relationship_context(
        effective_state,
        recent_events=tuple(reversed(events)),
    )


async def update_relationship_state(
    *,
    target: AIRelationshipTarget,
    sentiment: "AIMessageSentiment",
    is_tome: bool,
) -> None:
    """Apply relationship deltas derived from LLM sentiment analysis."""

    delta = derive_relationship_delta(
        sentiment=sentiment,
        is_private=target.is_private,
        is_tome=is_tome,
    )
    if delta is None:
        return

    await ai_relationship_service.apply_delta(
        platform=target.platform,
        group_id=target.group_id,
        user_id=target.user_id,
        delta=delta,
    )


def _format_relationship_event_line(event: "AIRelationshipEvent") -> str:
    reason = event.reason or "无明确原因"
    delta_sign = "+" if event.score_delta >= 0 else ""
    return (
        f"- [{event.event_type}] {delta_sign}{event.score_delta:.2f}"
        f" → {event.score_after:.2f}; {reason}"
    )
