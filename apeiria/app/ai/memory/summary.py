"""Pure helpers for deterministic summary memories."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition, AIMemoryKind

_MIN_MEMORIES_FOR_SUMMARY = 2


def build_summary_memory_content(
    memories: list[AIMemoryDefinition],
) -> str | None:
    """Build one deterministic summary memory from specific long-term memories."""

    detail_memories = [
        memory
        for memory in memories
        if (
            memory.memory_layer == "long_term"
            and not memory.is_ignored
            and memory.content.strip()
        )
    ]
    if len(detail_memories) < _MIN_MEMORIES_FOR_SUMMARY:
        return None

    ordered = sorted(
        detail_memories,
        key=lambda item: (
            _summary_priority(item.memory_kind),
            -item.salience,
            -item.confidence,
            item.created_at,
            item.memory_id,
        ),
    )
    lines = [f"- [{memory.memory_kind}] {memory.content}" for memory in ordered[:4]]
    return "Stable memory context:\n" + "\n".join(lines)


def _summary_priority(memory_kind: AIMemoryKind) -> int:
    priorities: dict[AIMemoryKind, int] = {
        "preference": 0,
        "relationship": 1,
        "fact": 2,
        "note": 3,
    }
    return priorities.get(memory_kind, 9)
