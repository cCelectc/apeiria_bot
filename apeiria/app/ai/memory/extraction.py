"""Structured long-term memory extraction helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from apeiria.app.ai.memory.models import (
    AIMemoryExtractionAction,
    AIMemoryExtractionCandidate,
    AIMemoryKind,
)

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition

_ALLOWED_MEMORY_KINDS: set[AIMemoryKind] = {
    "fact",
    "preference",
    "relationship",
    "note",
    "impression",
}
_MAX_CANDIDATES = 5
_PERSON_PROFILE_ALLOWED_KINDS: set[AIMemoryKind] = {
    "fact",
    "preference",
    "relationship",
    "impression",
}
_PERSON_PROFILE_MIN_CONFIDENCE = 0.8
_MAX_PERSON_PROFILE_CANDIDATES = 4


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
            '{"memories":[{"memory_kind":"preference|fact|relationship|note|impression","content":"...","action":"add|update|noop","target_memory_id":"optional-existing-id","confidence":0.0,"salience":0.0}]}',
            "Only include information that is useful in future conversations.",
            "Do not include transient requests, jokes, or uncertain guesses.",
            "Use the same language as the source message for content.",
            "Use action=noop when nothing should be stored for that row.",
            "Use action=update when the message changes or corrects an "
            "existing durable memory.",
            "Use memory_kind=impression for subjective observations about the "
            "user's personality, communication style, or character traits "
            "(e.g. enthusiastic, introverted, knowledgeable). "
            "Only extract impressions when there is clear behavioral evidence.",
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
        key = (candidate.memory_kind, candidate.content)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
        if len(candidates) >= _MAX_CANDIDATES:
            break
    return candidates


def select_person_profile_candidates(
    candidates: list[AIMemoryExtractionCandidate],
) -> list[AIMemoryExtractionCandidate]:
    """Choose high-precision candidates that should shape person profiles."""

    selected = [
        candidate
        for candidate in candidates
        if candidate.memory_kind in _PERSON_PROFILE_ALLOWED_KINDS
        and candidate.confidence >= _PERSON_PROFILE_MIN_CONFIDENCE
    ]
    selected.sort(
        key=lambda item: (item.confidence, item.salience, item.content),
        reverse=True,
    )
    return selected[:_MAX_PERSON_PROFILE_CANDIDATES]


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
    raw_memory_kind = row.get("memory_kind")
    content = row.get("content")
    if raw_memory_kind not in _ALLOWED_MEMORY_KINDS:
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    action = _coerce_action(row.get("action"))
    return AIMemoryExtractionCandidate(
        memory_kind=raw_memory_kind,
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
            f"- id={memory.memory_id}; kind={memory.memory_kind}; "
            f'content="{memory.content}"'
        )
        for memory in existing_memories[:8]
    ]
    if not lines:
        return "Existing memories: []"
    return "Existing memories:\n" + "\n".join(lines)
