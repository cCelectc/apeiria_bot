"""Pure helpers for capped relevance-ranked memory retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition, AIMemoryQuery


def _score_memory_item(
    memory: AIMemoryDefinition,
    query_text: str,
) -> tuple[float, float, float]:
    query_terms = {
        token.strip().lower()
        for token in query_text.split()
        if token.strip()
    }
    content_terms = {
        token.strip().lower()
        for token in memory.content.split()
        if token.strip()
    }
    overlap = len(query_terms & content_terms)
    return (
        float(overlap),
        float(memory.salience),
        float(memory.confidence),
    )


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
