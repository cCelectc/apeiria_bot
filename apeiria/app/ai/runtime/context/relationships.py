"""Runtime relationship steps for reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.relationship import derive_relationship_delta, project_emotion
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMessageSentiment
    from apeiria.ai.relationship import AIRelationshipEvent, AIRelationshipState
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True)
class AIRelationshipTarget:
    """Resolved relationship target for one runtime turn."""

    platform: str
    scene_id: str | None
    user_id: str
    is_private: bool


def build_relationship_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIRelationshipTarget:
    """Build one relationship target from the current conversation identity."""

    return AIRelationshipTarget(
        platform=identity.platform,
        scene_id=identity.scene_id,
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
    sections = [
        "关系好感只影响表达层：语气、措辞、主动性和互动距离。",
        "关系好感不得改变人格、事实、权限、工具授权、安全策略或记忆治理。",
        f"当前好感：{state.score:+d} / 范围 [-100, 100]，neutral=0",
        f"关系层级：{projection.tone}",
    ]
    if projection.style_modulation:
        sections.append("表达调制：")
        sections.extend(f"- {line}" for line in projection.style_modulation)
    if state.mood_tags:
        sections.append(f"近期互动氛围：{', '.join(state.mood_tags)}")
    if recent_events:
        sections.append("近期关系事件：")
        sections.extend(
            _format_relationship_event_line(event) for event in recent_events
        )
    return "\n".join(sections)


async def load_relationship_context(
    *,
    target: AIRelationshipTarget,
) -> str | None:
    """Load prompt-ready relationship context for the current target."""

    state = await ai_wiring.relationship_service.get_state(
        platform=target.platform,
        user_id=target.user_id,
    )
    effective_state = await ai_wiring.relationship_service.get_effective_state(
        platform=target.platform,
        user_id=target.user_id,
    )
    events = await ai_wiring.relationship_service.list_events(
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

    await ai_wiring.relationship_service.apply_delta(
        platform=target.platform,
        user_id=target.user_id,
        scene_id=target.scene_id,
        delta=delta,
    )


def _format_relationship_event_line(event: "AIRelationshipEvent") -> str:
    reason = event.reason or "无明确原因"
    delta_sign = "+" if event.score_delta >= 0 else ""
    return (
        f"- [{event.event_type}] {delta_sign}{event.score_delta}"
        f" -> {event.score_after}；{reason}"
    )
