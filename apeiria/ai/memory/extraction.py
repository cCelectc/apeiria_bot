"""Structured long-term memory extraction helpers."""

from __future__ import annotations

import json
from typing import Any

from apeiria.ai.memory.models import (
    AIMemoryExtractionAction,
    AIMemoryExtractionCandidate,
    AIMemoryExtractionResult,
    AIMemoryKind,
    AIMemoryScopeHint,
    AIMessageSentiment,
    AISentimentPolarity,
)

_ALLOWED_MEMORY_KINDS: set[AIMemoryKind] = {
    "fact",
    "preference",
    "relationship",
    "note",
    "impression",
}
_MAX_CANDIDATES = 5
_ALLOWED_SCOPE_HINTS: set[AIMemoryScopeHint] = {
    "auto",
    "scene",
    "participant",
    "user",
}
_ALLOWED_POLARITIES: set[AISentimentPolarity] = {
    "positive",
    "neutral",
    "negative",
    "playful",
}
_DEFAULT_SENTIMENT = AIMessageSentiment(polarity="neutral", intensity=0.0)


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
        scope_hint=_coerce_scope_hint(row.get("scope_hint")),
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


def _coerce_scope_hint(value: Any) -> AIMemoryScopeHint:
    if value in _ALLOWED_SCOPE_HINTS:
        return value
    return "auto"


def _coerce_optional_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
