"""LLM prompt construction and parsing for social judgment (Layer 3)."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    SocialJudgmentAction,
    SocialJudgmentInput,
    SocialJudgmentResult,
    SocialJudgmentToolMode,
)

_ALLOWED_ACTIONS: set[SocialJudgmentAction] = {
    "reply",
    "interject",
    "wait",
    "suppress",
}
_ALLOWED_TOOL_MODES: set[SocialJudgmentToolMode] = {"allow", "avoid"}

_JSON_SHAPE = (
    '{"action":"reply|interject|wait|suppress",'
    '"tool_mode":"allow|avoid","reason_codes":["short_code"],'
    '"reason_text":"one short explanation","evidence":'
    '{"cooldown_active":false,"low_value_message":false}}'
)


def build_social_judgment_prompt(
    judgment_input: SocialJudgmentInput,
) -> str:
    """Build the JSON-only prompt for the social judgment LLM call."""

    latest_user_msg = judgment_input.latest_user_turn_text or "<none>"
    conv_summary = judgment_input.conversation_summary or "<none>"
    rel_context = judgment_input.relationship_context or "<none>"
    persona_id = judgment_input.persona_id or "<none>"
    tool_names = ", ".join(judgment_input.available_tool_names) or "<none>"

    lines = [
        "Decide the assistant's social behavior for the current turn.",
        (
            "Optimize for social coherence, restraint, persona consistency, "
            "and avoiding a tool-brained feel."
        ),
        "Return strict JSON only with this shape:",
        _JSON_SHAPE,
    ]

    # Engagement-specific guidance
    if judgment_input.engagement_type == "direct":
        lines.extend(
            (
                (
                    "The user has directly addressed the bot (@mention or "
                    "private message).  Prefer action=reply unless the message "
                    "is empty filler, pure noise, or genuinely not worth "
                    "responding to — in that case use action=suppress."
                ),
            )
        )
    else:
        lines.extend(
            (
                (
                    "The bot was NOT directly addressed.  The default and most "
                    "common action should be action=suppress (stay silent).  "
                    "Only use action=interject when speaking without direct "
                    "address still has clear social value — the bot has "
                    "something genuinely relevant, funny, or helpful to add."
                ),
                (
                    "Do NOT interject just because the bot 'could' answer.  "
                    "Real people stay silent most of the time in group chats."
                ),
            )
        )

    lines.extend(
        (
            "Use action=reply for normal direct response.",
            (
                "Use action=interject only when speaking without strong direct "
                "address still has clear social value."
            ),
            (
                "Use action=wait when the assistant should hold off for now "
                "but the conversation may continue soon."
            ),
            "Use action=suppress when the assistant should stay silent.",
            (
                "Use tool_mode=allow only when tools are genuinely needed; "
                "otherwise use avoid."
            ),
            f"Scene type: {judgment_input.scene_type}",
            f"Runtime mode: {judgment_input.runtime_mode}",
            f"Engagement type: {judgment_input.engagement_type}",
            f"Message text: {judgment_input.message_text}",
            f"Latest user turn text: {latest_user_msg}",
            f"Conversation summary: {conv_summary}",
            f"Relationship context: {rel_context}",
            f"Persona id: {persona_id}",
            f"Available tool names: {tool_names}",
            f"Recent turn count: {judgment_input.recent_turn_count}",
            f"Recent bot turn count: {judgment_input.recent_bot_turn_count}",
            f"Consecutive silence count: {judgment_input.consecutive_silence_count}",
            f"Current time: {judgment_input.current_time.isoformat()}",
        )
    )

    if judgment_input.initiative_budget_score is not None:
        lines.append(
            f"Initiative budget score: {judgment_input.initiative_budget_score:.2f}"
        )

    return "\n".join(lines)


def parse_social_judgment_response(
    content: str,
    *,
    fallback: SocialJudgmentResult,
) -> SocialJudgmentResult:
    """Parse model JSON into a social judgment, falling back if invalid."""

    parsed = _parse_json_object(content)
    action = parsed.get("action")
    tool_mode = parsed.get("tool_mode")
    reason_codes = parsed.get("reason_codes")
    reason_text = parsed.get("reason_text")
    evidence = parsed.get("evidence")

    if action not in _ALLOWED_ACTIONS:
        return fallback
    if tool_mode not in _ALLOWED_TOOL_MODES:
        return fallback
    if not isinstance(reason_codes, list):
        return fallback
    cleaned_codes = tuple(
        item.strip() for item in reason_codes if isinstance(item, str) and item.strip()
    )
    if not cleaned_codes:
        return fallback
    if not isinstance(reason_text, str) or not reason_text.strip():
        return fallback
    if not isinstance(evidence, dict):
        evidence = {}

    should_speak = action in {"reply", "interject"}
    return SocialJudgmentResult(
        action=action,
        should_speak=should_speak,
        should_interject=action == "interject",
        should_wait=action == "wait",
        tool_mode=tool_mode,
        reason_codes=cleaned_codes,
        reason_text=reason_text.strip(),
        evidence=evidence,
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if not stripped:
        return {}
    if stripped.startswith("```"):
        stripped = _strip_code_fence(stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _strip_code_fence(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
