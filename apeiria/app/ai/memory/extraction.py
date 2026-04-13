"""Structured long-term memory extraction helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from apeiria.app.ai.memory.models import (
    AIMemoryExtractionAction,
    AIMemoryExtractionCandidate,
    AIMemoryType,
)

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition

_ALLOWED_MEMORY_TYPES: set[AIMemoryType] = {
    "fact",
    "preference",
    "relationship",
    "episode",
    "summary",
    "operator_note",
}
_MAX_CANDIDATES = 5


def build_memory_extraction_prompt(
    message_text: str,
    *,
    existing_memories: tuple[AIMemoryDefinition, ...] = (),
) -> str:
    """Build the JSON-only extraction prompt used by the memory task model."""

    return "\n".join(
        (
            "Extract durable long-term memory candidates from the user message.",
            "Return strict JSON only, with this shape:",
            '{"memories":[{"memory_type":"preference|fact|relationship|episode|summary|operator_note","content":"...","action":"add|update|noop","target_memory_id":"optional-existing-id","confidence":0.0,"salience":0.0}]}',
            "Only include information that is useful in future conversations.",
            "Do not include transient requests, jokes, or uncertain guesses.",
            "Use the same language as the source message for content.",
            "Use action=noop when nothing should be stored for that row.",
            "Use action=update when the message changes or corrects an "
            "existing durable memory.",
            _format_existing_memories(existing_memories),
            'If there is nothing durable, return {"memories":[]}.',
            f"User message: {message_text}",
        )
    )


def parse_memory_extraction_response(
    content: str,
) -> list[AIMemoryExtractionCandidate]:
    """Parse model JSON into bounded memory candidates."""

    parsed = _parse_json_object(content)
    rows = parsed.get("memories")
    if not isinstance(rows, list):
        return []

    candidates: list[AIMemoryExtractionCandidate] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = _parse_candidate(row)
        if candidate is None:
            continue
        key = (candidate.memory_type, candidate.content)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        if len(candidates) >= _MAX_CANDIDATES:
            break
    return candidates


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


def _parse_candidate(row: dict[str, Any]) -> AIMemoryExtractionCandidate | None:
    memory_type = row.get("memory_type")
    content = row.get("content")
    if memory_type not in _ALLOWED_MEMORY_TYPES:
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    action = _coerce_action(row.get("action"))
    return AIMemoryExtractionCandidate(
        memory_type=memory_type,
        content=content.strip(),
        action=action,
        target_memory_id=_coerce_optional_id(row.get("target_memory_id")),
        confidence=_coerce_score(row.get("confidence"), default=0.7),
        salience=_coerce_score(row.get("salience"), default=0.6),
    )


def _coerce_score(value: Any, *, default: float) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return default


def _coerce_action(value: Any) -> AIMemoryExtractionAction:
    if value == "noop":
        return "noop"
    if value == "update":
        return "update"
    return "add"


def _coerce_optional_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _format_existing_memories(
    existing_memories: tuple[AIMemoryDefinition, ...],
) -> str:
    if not existing_memories:
        return "Existing memories: []"
    lines = [
        (
            f"- id={memory.memory_id}; type={memory.memory_type}; "
            f'content="{memory.content}"'
        )
        for memory in existing_memories[:8]
        if memory.memory_type != "summary"
    ]
    if not lines:
        return "Existing memories: []"
    return "Existing memories:\n" + "\n".join(lines)
