"""Pure heuristic extraction of long-term memory candidates from messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryType

_PREFERENCE_PATTERNS = (
    re.compile(r"我喜欢(?P<value>[^，。！？!?]{1,24})"),
    re.compile(r"我爱(?P<value>[^，。！？!?]{1,24})"),
)
_FACT_PATTERNS = (
    re.compile(r"我是(?P<value>[^，。！？!?]{1,24})"),
    re.compile(r"我在(?P<value>[^，。！？!?]{1,24})"),
)


@dataclass(frozen=True)
class AIMemoryExtractionCandidate:
    """One heuristic memory candidate extracted from a user message."""

    memory_type: AIMemoryType
    content: str


def extract_memory_candidates(text: str) -> list[AIMemoryExtractionCandidate]:
    """Extract conservative long-term memory candidates from one message."""

    normalized = text.strip()
    if not normalized:
        return []

    candidates: list[AIMemoryExtractionCandidate] = []
    candidates.extend(
        _extract_candidates(
            normalized,
            patterns=_PREFERENCE_PATTERNS,
            memory_type="preference",
            prefix="喜欢",
        )
    )
    candidates.extend(
        _extract_candidates(
            normalized,
            patterns=_FACT_PATTERNS,
            memory_type="fact",
            prefix=None,
        )
    )

    seen: set[tuple[str, str]] = set()
    deduped: list[AIMemoryExtractionCandidate] = []
    for candidate in candidates:
        key = (candidate.memory_type, candidate.content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:2]


def _extract_candidates(
    text: str,
    *,
    patterns: tuple[re.Pattern[str], ...],
    memory_type: AIMemoryType,
    prefix: str | None,
) -> list[AIMemoryExtractionCandidate]:
    candidates: list[AIMemoryExtractionCandidate] = []
    for pattern in patterns:
        match = pattern.search(text)
        if match is None:
            continue
        value = match.group("value").strip()
        if not value:
            continue
        content = f"{prefix}{value}" if prefix else value
        candidates.append(
            AIMemoryExtractionCandidate(
                memory_type=memory_type,
                content=content,
            )
        )
    return candidates
