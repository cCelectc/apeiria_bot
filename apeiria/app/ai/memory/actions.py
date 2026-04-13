"""Pure helpers for applying structured memory actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from apeiria.app.ai.memory.models import (
        AIMemoryDefinition,
        AIMemoryExtractionCandidate,
    )

MemoryWriteAction = Literal["add", "update"]


@dataclass(frozen=True)
class AIMemoryWritePlan:
    """One resolved memory write operation."""

    action: MemoryWriteAction
    candidate: AIMemoryExtractionCandidate
    target_memory_id: str | None = None


def build_memory_write_plans(
    existing_memories: list[AIMemoryDefinition],
    candidates: list[AIMemoryExtractionCandidate],
) -> list[AIMemoryWritePlan]:
    """Resolve extracted candidates into add/update operations."""

    plans: list[AIMemoryWritePlan] = []
    for candidate in candidates:
        if candidate.action == "noop":
            continue
        if candidate.action == "update":
            target_memory_id = resolve_update_target_memory_id(
                existing_memories,
                candidate,
            )
            if target_memory_id is not None:
                plans.append(
                    AIMemoryWritePlan(
                        action="update",
                        candidate=candidate,
                        target_memory_id=target_memory_id,
                    )
                )
                continue
        plans.append(AIMemoryWritePlan(action="add", candidate=candidate))
    return plans


def resolve_update_target_memory_id(
    existing_memories: list[AIMemoryDefinition],
    candidate: AIMemoryExtractionCandidate,
) -> str | None:
    """Resolve which existing memory should be updated, if any."""

    if candidate.target_memory_id is not None:
        for memory in existing_memories:
            if memory.memory_id == candidate.target_memory_id:
                return memory.memory_id

    same_type_memories = [
        memory
        for memory in existing_memories
        if memory.memory_type == candidate.memory_type
        and not (
            candidate.memory_type == "note"
            and memory.content.startswith("Known stable context:\n")
        )
    ]
    if not same_type_memories:
        return None

    ordered = sorted(
        same_type_memories,
        key=lambda memory: (
            memory.last_recalled_at or memory.created_at,
            memory.created_at,
            memory.memory_id,
        ),
        reverse=True,
    )
    return ordered[0].memory_id
