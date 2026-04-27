"""Social judgment prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .models import PromptPacket, PromptSection

if TYPE_CHECKING:
    from datetime import datetime

SocialEngagementType = Literal["direct", "ambient"]

_JSON_SHAPE = (
    '{"action":"reply|interject|wait|suppress",'
    '"tool_mode":"allow|avoid","reason_codes":["short_code"],'
    '"reason_text":"one short explanation","evidence":'
    '{"cooldown_active":false,"low_value_message":false}}'
)


@dataclass(frozen=True)
class SocialJudgmentPromptInput:
    """Prompt-facing materials for one social judgment call."""

    scene_type: str
    runtime_mode: str
    engagement_type: SocialEngagementType | str
    message_text: str
    latest_user_turn_text: str | None
    conversation_summary: str | None
    relationship_context: str | None
    persona_id: str | None
    available_tool_names: tuple[str, ...]
    recent_turn_count: int
    recent_bot_turn_count: int
    consecutive_silence_count: int
    current_time: "datetime"
    initiative_budget_score: float | None = None


def build_social_judgment_packet(
    inputs: SocialJudgmentPromptInput,
) -> PromptPacket:
    """Build a packet for deciding whether and how to speak."""

    sections = [
        PromptSection(
            role="system",
            name="Instruction",
            content="\n".join(
                (
                    "Decide the assistant's social behavior for the current turn.",
                    (
                        "Optimize for social coherence, restraint, persona "
                        "consistency, and avoiding a tool-brained feel."
                    ),
                )
            ),
        ),
        PromptSection(
            role="system",
            name="EngagementPolicy",
            content=_build_engagement_policy(inputs),
        ),
        PromptSection(
            role="system",
            name="ActionPolicy",
            content="\n".join(
                (
                    "Use action=reply for normal direct response.",
                    (
                        "Use action=interject only when speaking without strong "
                        "direct address still has clear social value."
                    ),
                    (
                        "Use action=wait when the assistant should hold off for "
                        "now but the conversation may continue soon."
                    ),
                    "Use action=suppress when the assistant should stay silent.",
                    (
                        "Use tool_mode=allow only when tools are genuinely needed; "
                        "otherwise use avoid."
                    ),
                )
            ),
        ),
        PromptSection(
            role="user",
            name="Context",
            content=_build_context(inputs),
        ),
        PromptSection(
            role="user",
            name="OutputContract",
            content="\n".join(
                (
                    "Return strict JSON only with this shape:",
                    _JSON_SHAPE,
                )
            ),
        ),
    ]
    return PromptPacket(purpose="social_judgment", sections=tuple(sections))


def _build_engagement_policy(inputs: SocialJudgmentPromptInput) -> str:
    if inputs.engagement_type == "direct":
        return (
            "The user has directly addressed the bot (@mention or private message). "
            "Prefer action=reply unless the message is empty filler, pure noise, "
            "or genuinely not worth responding to - in that case use action=suppress."
        )
    return "\n".join(
        (
            (
                "The bot was NOT directly addressed. The default and most common "
                "action should be action=suppress (stay silent). Only use "
                "action=interject when speaking without direct address still has "
                "clear social value - the bot has something genuinely relevant, "
                "funny, or helpful to add."
            ),
            (
                "Do NOT interject just because the bot 'could' answer. Real people "
                "stay silent most of the time in group chats."
            ),
        )
    )


def _build_context(inputs: SocialJudgmentPromptInput) -> str:
    tool_names = ", ".join(inputs.available_tool_names) or "<none>"
    lines = [
        f"Scene type: {inputs.scene_type}",
        f"Runtime mode: {inputs.runtime_mode}",
        f"Engagement type: {inputs.engagement_type}",
        f"Message text: {inputs.message_text}",
        f"Latest user turn text: {inputs.latest_user_turn_text or '<none>'}",
        f"Conversation summary: {inputs.conversation_summary or '<none>'}",
        f"Relationship context: {inputs.relationship_context or '<none>'}",
        f"Persona id: {inputs.persona_id or '<none>'}",
        f"Available tool names: {tool_names}",
        f"Recent turn count: {inputs.recent_turn_count}",
        f"Recent bot turn count: {inputs.recent_bot_turn_count}",
        f"Consecutive silence count: {inputs.consecutive_silence_count}",
        f"Current time: {inputs.current_time.isoformat()}",
    ]
    if inputs.initiative_budget_score is not None:
        lines.append(f"Initiative budget score: {inputs.initiative_budget_score:.2f}")
    return "\n".join(lines)
