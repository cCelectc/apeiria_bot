"""LLM-backed parsing helpers for social-policy decisions."""

from __future__ import annotations

import json
from typing import Any

from apeiria.app.ai.social_policy.models import (
    AISocialPolicyAction,
    AISocialPolicyDecision,
    AISocialPolicyInput,
    AISocialPolicyToolMode,
)

_ALLOWED_ACTIONS: set[AISocialPolicyAction] = {
    "reply",
    "interject",
    "wait",
    "suppress",
}
_ALLOWED_TOOL_MODES: set[AISocialPolicyToolMode] = {"allow", "avoid"}
_JSON_SHAPE = (
    '{"action":"reply|interject|wait|suppress",'
    '"tool_mode":"allow|avoid","reason_codes":["short_code"],'
    '"reason_text":"one short explanation","evidence":'
    '{"cooldown_active":false,"low_value_message":false}}'
)


def build_social_policy_prompt(policy_input: AISocialPolicyInput) -> str:
    """Build the JSON-only prompt for social-policy judgment."""

    latest_user_message = policy_input.latest_user_turn_text or "<none>"
    conversation_summary = policy_input.conversation_summary or "<none>"
    relationship_context = policy_input.relationship_context or "<none>"
    persona_id = policy_input.persona_id or "<none>"
    tool_names = ", ".join(policy_input.available_tool_names) or "<none>"

    return "\n".join(
        (
            "Decide the assistant's social behavior for the current turn.",
            (
                "Optimize for social coherence, restraint, persona consistency, "
                "and avoiding a tool-brained feel."
            ),
            "Return strict JSON only with this shape:",
            _JSON_SHAPE,
            "Use action=reply for normal direct response.",
            (
                "Use action=interject only when speaking without strong direct "
                "address still has clear social value."
            ),
            (
                "Use action=wait when the assistant should hold off for now but "
                "the conversation may continue soon."
            ),
            "Use action=suppress when the assistant should stay silent.",
            (
                "Use tool_mode=allow only when tools are genuinely needed; "
                "otherwise use avoid."
            ),
            f"Scene type: {policy_input.scene_type}",
            f"Runtime mode: {policy_input.runtime_mode}",
            f"Message text: {policy_input.message_text}",
            f"Latest user turn text: {latest_user_message}",
            f"Conversation summary: {conversation_summary}",
            f"Relationship context: {relationship_context}",
            f"Persona id: {persona_id}",
            f"Available tool names: {tool_names}",
            f"Recent turn count: {policy_input.recent_turn_count}",
            f"Recent bot turn count: {policy_input.recent_bot_turn_count}",
            f"Is direct wake: {policy_input.is_direct_wake}",
            f"Current time: {policy_input.current_time.isoformat()}",
        )
    )


def parse_social_policy_response(
    content: str,
    *,
    fallback: AISocialPolicyDecision,
) -> AISocialPolicyDecision:
    """Parse model JSON into a social-policy decision, falling back if invalid."""

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
        item.strip()
        for item in reason_codes
        if isinstance(item, str) and item.strip()
    )
    if not cleaned_codes:
        return fallback
    if not isinstance(reason_text, str) or not reason_text.strip():
        return fallback
    if not isinstance(evidence, dict):
        evidence = {}

    should_speak = action in {"reply", "interject"}
    return AISocialPolicyDecision(
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
