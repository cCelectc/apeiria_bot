"""Pure helpers for capped relevance-ranked memory retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition, AIMemoryQuery

BIGRAM_SIZE = 2


def _score_memory_item(
    memory: AIMemoryDefinition,
    query_text: str,
) -> tuple[float, float, float, float]:
    query_terms = _extract_terms(query_text)
    content_terms = _extract_terms(memory.content)
    overlap = len(query_terms & content_terms)
    return (
        float(overlap),
        _memory_type_score(memory),
        float(memory.salience),
        float(memory.confidence),
    )


def _extract_terms(text: str) -> set[str]:
    normalized = text.strip().lower()
    if not normalized:
        return set()

    terms = {
        token.strip()
        for token in normalized.split()
        if token.strip()
    }
    if not terms:
        terms.add(normalized)
    if len(normalized) >= BIGRAM_SIZE:
        terms.update(
            normalized[index : index + BIGRAM_SIZE]
            for index in range(len(normalized) - BIGRAM_SIZE + 1)
            if normalized[index : index + BIGRAM_SIZE].strip()
        )
    return terms


def rank_memory_items(
    items: list[AIMemoryDefinition],
    query: AIMemoryQuery,
) -> list[AIMemoryDefinition]:
    """Return the top ranked memory items for one retrieval query."""

    if query.limit <= 0:
        return []

    filtered = [
        item
        for item in items
        if item.subject_type == query.subject_type
        and item.subject_id == query.subject_id
    ]

    ranked = sorted(
        filtered,
        key=lambda item: _score_memory_item(item, query.query_text),
        reverse=True,
    )
    return ranked[: query.limit]


def _memory_type_score(memory: AIMemoryDefinition) -> float:
    scores = {
        "preference": 0.4,
        "relationship": 0.3,
        "fact": 0.2,
        "episode": 0.1,
        "operator_note": 0.05,
        "summary": -0.1,
    }
    return scores.get(memory.memory_type, 0.0)
