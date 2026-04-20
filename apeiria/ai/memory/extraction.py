"""Structured long-term memory extraction helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from apeiria.ai.memory.models import (
    AIMemoryExtractionAction,
    AIMemoryExtractionCandidate,
    AIMemoryExtractionResult,
    AIMemoryKind,
    AIMessageSentiment,
    AISentimentPolarity,
)

if TYPE_CHECKING:
    from apeiria.ai.memory.models import AIMemoryDefinition

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
_ALLOWED_POLARITIES: set[AISentimentPolarity] = {
    "positive",
    "neutral",
    "negative",
    "playful",
}
_DEFAULT_SENTIMENT = AIMessageSentiment(polarity="neutral", intensity=0.0)


def build_memory_extraction_prompt(
    message_text: str,
    *,
    existing_memories: tuple["AIMemoryDefinition", ...] = (),
) -> str:
    """Build the JSON-only extraction prompt used by the memory task model."""

    return "\n".join(
        (
            "Analyze the user message and return strict JSON with this shape:",
            "{",
            '  "memories": [{"memory_kind": "...", "content": "...",',
            '    "action": "add|update|noop",',
            '    "target_memory_id": "optional-existing-id",',
            '    "confidence": 0.0, "salience": 0.0}],',
            '  "sentiment": {"polarity": "...", "intensity": 0.0},',
            '  "self_introduction_name": null',
            "}",
            "",
            "Allowed memory_kind values: "
            "preference, fact, relationship, note, impression.",
            "Allowed sentiment polarity values: positive, neutral, negative, playful.",
            "",
            "## Memory extraction rules",
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
            "",
            "## Sentiment analysis rules",
            "Analyze the overall emotional tone of the message.",
            "polarity: positive (grateful, happy, affectionate), "
            "negative (angry, annoyed, hostile), "
            "playful (teasing, joking, lighthearted), "
            "neutral (informational, calm, ambiguous).",
            "intensity: 0.0 (barely perceptible) to 1.0 (very strong).",
            "",
            "## Self-introduction name",
            "If the user introduces themselves by name "
            '(e.g. "叫我小明", "I\'m Alice", "你可以喊我阿澈"), '
            "extract the name into self_introduction_name. Otherwise null.",
            "",
            _format_existing_memories(existing_memories),
            'If there is nothing durable, return {"memories":[], '
            '"sentiment": {"polarity": "neutral", "intensity": 0.0}, '
            '"self_introduction_name": null}.',
            f"User message: {message_text}",
        )
    )


def parse_memory_extraction_response(
    content: str,
) -> AIMemoryExtractionResult:
    """Parse model JSON into bounded memory candidates + sentiment + name."""

    parsed = _parse_json_object(content)

    candidates = _parse_candidates(parsed)
    sentiment = _parse_sentiment(parsed)
    self_introduction_name = _parse_self_introduction_name(parsed)

    return AIMemoryExtractionResult(
        candidates=candidates,
        sentiment=sentiment,
        self_introduction_name=self_introduction_name,
    )


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


def _parse_candidates(
    parsed: dict[str, Any],
) -> list[AIMemoryExtractionCandidate]:
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


def _parse_sentiment(parsed: dict[str, Any]) -> AIMessageSentiment:
    raw = parsed.get("sentiment")
    if not isinstance(raw, dict):
        return _DEFAULT_SENTIMENT
    polarity = raw.get("polarity")
    if polarity not in _ALLOWED_POLARITIES:
        return _DEFAULT_SENTIMENT
    return AIMessageSentiment(
        polarity=polarity,
        intensity=_coerce_score(raw.get("intensity"), default=0.0),
    )


def _parse_self_introduction_name(parsed: dict[str, Any]) -> str | None:
    value = parsed.get("self_introduction_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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
    existing_memories: tuple["AIMemoryDefinition", ...],
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
