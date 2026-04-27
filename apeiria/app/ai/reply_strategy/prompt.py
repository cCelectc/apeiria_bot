"""LLM response parsing for social judgment (Layer 3)."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    SocialJudgmentAction,
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
