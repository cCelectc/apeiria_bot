"""Pure helpers for deterministic summary memories."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import AIMemoryDefinition, AIMemoryType

_MIN_MEMORIES_FOR_SUMMARY = 2
SUMMARY_NOTE_PREFIX = "Known stable context:\n"


def build_summary_memory_content(
    memories: list[AIMemoryDefinition],
) -> str | None:
    """Build one deterministic summary memory from specific long-term memories."""

    detail_memories = [
        memory
        for memory in memories
        if memory.content.strip() and not _is_summary_note(memory)
    ]
    if len(detail_memories) < _MIN_MEMORIES_FOR_SUMMARY:
        return None

    ordered = sorted(
        detail_memories,
        key=lambda item: (
            _summary_priority(item.memory_type),
            -item.salience,
            -item.confidence,
            item.created_at,
            item.memory_id,
        ),
    )
    lines = [f"- [{memory.memory_type}] {memory.content}" for memory in ordered[:4]]
    return SUMMARY_NOTE_PREFIX + "\n".join(lines)


def _summary_priority(memory_type: AIMemoryType) -> int:
    priorities: dict[AIMemoryType, int] = {
        "preference": 0,
        "relationship": 1,
        "fact": 2,
        "note": 3,
    }
    return priorities.get(memory_type, 9)


def _is_summary_note(memory: AIMemoryDefinition) -> bool:
    return (
        memory.memory_type == "note"
        and memory.content.startswith(SUMMARY_NOTE_PREFIX)
    )
