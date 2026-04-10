"""Runtime memory steps extracted from the orchestration compatibility layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.memory.extraction import extract_memory_candidates
from apeiria.app.ai.memory.models import AIMemoryQuery
from apeiria.app.ai.memory.service import ai_memory_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import AIConversationIdentity
    from apeiria.app.ai.memory.models import AIMemoryDefinition


@dataclass(frozen=True)
class AIMemoryRecallTarget:
    """One memory retrieval boundary for reply runtime."""

    subject_type: str
    subject_id: str


_MEMORY_TYPE_LIMITS: dict[str, int] = {
    "preference": 2,
    "relationship": 1,
    "episode": 1,
    "fact": 1,
    "summary": 1,
    "operator_note": 1,
}
_MAX_RECALLED_MEMORIES = 4


def build_memory_targets(
    identity: "AIConversationIdentity",
    user_id: str,
) -> list[AIMemoryRecallTarget]:
    """Build memory lookup targets for the current runtime turn."""

    targets = [
        AIMemoryRecallTarget(
            subject_type="conversation",
            subject_id=identity.conversation_id,
        )
    ]
    effective_user_id = identity.subject_user_id or user_id
    if effective_user_id:
        targets.append(
            AIMemoryRecallTarget(
                subject_type="user",
                subject_id=effective_user_id,
            )
        )
    return targets


def apply_memory_budget(
    memories: list["AIMemoryDefinition"],
) -> list["AIMemoryDefinition"]:
    """Apply a simple per-type recall budget for the prompt window."""

    selected: list[AIMemoryDefinition] = []
    selected_ids: set[str] = set()
    type_counts: dict[str, int] = {}

    for memory in memories:
        type_limit = _MEMORY_TYPE_LIMITS.get(memory.memory_type, 1)
        if type_counts.get(memory.memory_type, 0) >= type_limit:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        type_counts[memory.memory_type] = type_counts.get(memory.memory_type, 0) + 1
        if len(selected) >= _MAX_RECALLED_MEMORIES:
            return selected

    for memory in memories:
        if memory.memory_id in selected_ids:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        if len(selected) >= _MAX_RECALLED_MEMORIES:
            break
    return selected


async def recall_memories(
    session: "AsyncSession",
    *,
    identity: "AIConversationIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Recall memories for the current runtime turn."""

    recalled: list[AIMemoryDefinition] = []
    seen_ids: set[str] = set()
    for target in build_memory_targets(identity, user_id):
        rows = await ai_memory_service.recall_memories(
            session,
            AIMemoryQuery(
                subject_type=target.subject_type,
                subject_id=target.subject_id,
                query_text=query_text,
                limit=3,
            ),
        )
        for row in rows:
            if row.memory_id in seen_ids:
                continue
            seen_ids.add(row.memory_id)
            recalled.append(row)
    return apply_memory_budget(recalled)


async def store_extracted_memories(
    session: "AsyncSession",
    *,
    identity: "AIConversationIdentity",
    user_id: str,
    message_text: str,
    source_turn_id: str | None,
) -> None:
    """Extract and store lightweight memory candidates from one user message."""

    subject_id = identity.subject_user_id or user_id
    candidates = extract_memory_candidates(message_text)
    if not candidates:
        return

    await ai_memory_service.remember_candidates(
        session,
        subject_type="user",
        subject_id=subject_id,
        source_turn_id=source_turn_id,
        candidates=candidates,
    )
