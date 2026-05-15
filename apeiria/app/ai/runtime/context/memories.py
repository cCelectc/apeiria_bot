"""Runtime memory steps for reply orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.ai.memory import (
    AIMemoryLayer,
    AIMemoryQuery,
    AIMemoryRetrievalDiagnostics,
    AIMemoryRetrievalSelection,
    ai_memory_service,
)
from apeiria.ai.memory.governance import decide_candidate_scope
from apeiria.app.ai.runtime.context.memory_extraction import extract_memory_from_message
from apeiria.app.ai.runtime.context.profiles import ingest_profile_from_message
from apeiria.conversation.identity import build_participant_subject_id

if TYPE_CHECKING:
    from apeiria.ai.memory import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryExtractionCandidate,
        AIMemoryExtractionResult,
    )
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass(frozen=True)
class AIMemoryRecallAnchor:
    """One memory retrieval anchor for reply runtime."""

    anchor_type: "AIMemoryAnchorType"
    anchor_id: str


@dataclass(frozen=True)
class AIMemoryWriteAnchor:
    """One persistent memory write anchor for one runtime turn."""

    anchor_type: "AIMemoryAnchorType"
    anchor_id: str


_MEMORY_KIND_LIMITS: dict[str, int] = {
    "preference": 2,
    "relationship": 1,
    "fact": 1,
    "note": 1,
}
_LAYER_RECALL_LIMITS: dict[AIMemoryLayer, int] = {
    "operator": 2,
    "summary": 2,
    "long_term": 4,
    "knowledge": 3,
}
_RECALL_LAYER_ORDER: tuple[AIMemoryLayer, ...] = (
    "operator",
    "summary",
    "long_term",
    "knowledge",
)


def build_memory_anchors(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> list[AIMemoryRecallAnchor]:
    """Build anchor lookup order for the current runtime turn."""

    anchors = [
        AIMemoryRecallAnchor(
            anchor_type="scene",
            anchor_id=identity.session_id,
        )
    ]
    effective_user_id = identity.subject_id or user_id
    if identity.scene_type == "group" and identity.scene_id and effective_user_id:
        anchors.append(
            AIMemoryRecallAnchor(
                anchor_type="participant",
                anchor_id=build_participant_subject_id(
                    scene_type=identity.scene_type,
                    scene_id=identity.scene_id,
                    user_id=effective_user_id,
                ),
            )
        )
    if effective_user_id:
        anchors.append(
            AIMemoryRecallAnchor(
                anchor_type="user",
                anchor_id=effective_user_id,
            )
        )
    return anchors


def build_memory_write_anchors(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> tuple[AIMemoryWriteAnchor, ...]:
    """Build available persistent storage anchors for one runtime turn."""

    return tuple(
        AIMemoryWriteAnchor(anchor_type=anchor.anchor_type, anchor_id=anchor.anchor_id)
        for anchor in build_memory_anchors(identity, user_id)
    )


def select_memory_write_anchor(
    *,
    identity: "ChatSessionIdentity",
    candidate: "AIMemoryExtractionCandidate",
    write_anchors: tuple[AIMemoryWriteAnchor, ...],
) -> AIMemoryWriteAnchor | None:
    """Choose the narrowest reasonable scope for one automatic candidate."""

    target_scope = decide_candidate_scope(
        candidate,
        scene_type=identity.scene_type,
    )
    return _anchor_for_scope_hint(target_scope, write_anchors)


def _anchor_for_scope_hint(
    scope_hint: "AIMemoryAnchorType",
    write_anchors: tuple[AIMemoryWriteAnchor, ...],
) -> AIMemoryWriteAnchor | None:
    for anchor in write_anchors:
        if anchor.anchor_type == scope_hint:
            return anchor
    return None


def apply_memory_budget(
    memories: list["AIMemoryDefinition"],
    *,
    max_memories: int,
) -> list["AIMemoryDefinition"]:
    """Apply a simple per-kind recall budget for the prompt window."""

    selected: list[AIMemoryDefinition] = []
    selected_ids: set[str] = set()
    kind_counts: dict[str, int] = {}

    for memory in memories:
        kind_limit = _MEMORY_KIND_LIMITS.get(memory.memory_kind, 1)
        if kind_counts.get(memory.memory_kind, 0) >= kind_limit:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        kind_counts[memory.memory_kind] = kind_counts.get(memory.memory_kind, 0) + 1
        if len(selected) >= max_memories:
            return selected

    for memory in memories:
        if memory.memory_id in selected_ids:
            continue
        selected.append(memory)
        selected_ids.add(memory.memory_id)
        if len(selected) >= max_memories:
            break
    return selected


async def recall_memories(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Recall memories for the current runtime turn."""

    return await _retrieve_memories(
        identity=identity,
        user_id=user_id,
        query_text=query_text,
        mutate_recall=True,
    )


async def retrieve_memories_for_context(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Retrieve prompt memories without mutating recall timestamps."""

    return await _retrieve_memories(
        identity=identity,
        user_id=user_id,
        query_text=query_text,
        mutate_recall=False,
    )


async def record_live_memory_recall(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> None:
    """Stamp live recall timestamps outside read-oriented context assembly."""

    for memory_layer in _RECALL_LAYER_ORDER:
        if memory_layer == "knowledge":
            continue
        await _collect_layer_memories(
            identity=identity,
            user_id=user_id,
            query_text=query_text,
            memory_layer=memory_layer,
            mutate_recall=True,
        )


async def _retrieve_memories(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
    mutate_recall: bool,
) -> list["AIMemoryDefinition"]:
    """Retrieve runtime memories, optionally applying live recall mutation."""

    recalled: list[AIMemoryDefinition] = []
    diagnostics = await retrieve_memory_diagnostics_for_context(
        identity=identity,
        user_id=user_id,
        query_text=query_text,
    )
    recalled = [
        selection.memory
        for selection in diagnostics.selected
        if selection.is_prompt_visible
    ]
    if mutate_recall and recalled:
        await ai_memory_service.mark_memories_recalled(
            memory_ids=[memory.memory_id for memory in recalled],
            recalled_at=datetime.now(timezone.utc),
        )
    return recalled


async def retrieve_memory_diagnostics_for_context(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> "AIMemoryRetrievalDiagnostics":
    """Retrieve scoped memory selections with diagnostics for one runtime turn."""

    selected: list[AIMemoryRetrievalSelection] = []
    excluded: list[AIMemoryRetrievalSelection] = []
    seen_ids: set[str] = set()
    scope_rank = 0
    for memory_layer in _RECALL_LAYER_ORDER:
        if memory_layer == "knowledge":
            memories = await ai_memory_service.retrieve_knowledge_memories(
                targets=_build_knowledge_targets(identity, user_id),
                query_text=query_text,
                limit=_LAYER_RECALL_LIMITS[memory_layer],
            )
            for memory in apply_memory_budget(
                [item for item in memories if item.memory_id not in seen_ids],
                max_memories=_LAYER_RECALL_LIMITS[memory_layer],
            ):
                seen_ids.add(memory.memory_id)
                selected.append(
                    AIMemoryRetrievalSelection(
                        memory=memory,
                        use_mode=memory.default_use_mode,
                        scope_rank=scope_rank,
                    )
                )
            scope_rank += 1
            continue
        for anchor in build_memory_anchors(identity, user_id):
            query = AIMemoryQuery(
                anchor_type=anchor.anchor_type,
                anchor_id=anchor.anchor_id,
                query_text=query_text,
                limit=_LAYER_RECALL_LIMITS[memory_layer],
                memory_layer=memory_layer,
            )
            result = await ai_memory_service.retrieve_memory_selections(query)
            for item in result.selected:
                if item.memory.memory_id in seen_ids:
                    continue
                seen_ids.add(item.memory.memory_id)
                selected.append(
                    AIMemoryRetrievalSelection(
                        memory=item.memory,
                        use_mode=item.use_mode,
                        scope_rank=scope_rank,
                    )
                )
            excluded.extend(result.excluded)
            scope_rank += 1
    return AIMemoryRetrievalDiagnostics(
        selected=tuple(selected),
        excluded=tuple(excluded),
    )


async def retrieve_memories_for_preview(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Retrieve preview memories without mutating recall timestamps."""

    return await retrieve_memories_for_context(
        identity=identity,
        user_id=user_id,
        query_text=query_text,
    )


async def _collect_layer_memories(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
    memory_layer: AIMemoryLayer,
    mutate_recall: bool,
) -> list["AIMemoryDefinition"]:
    rows_for_layer: list[AIMemoryDefinition] = []
    seen_ids: set[str] = set()
    for anchor in build_memory_anchors(identity, user_id):
        query = AIMemoryQuery(
            anchor_type=anchor.anchor_type,
            anchor_id=anchor.anchor_id,
            query_text=query_text,
            limit=3,
            memory_layer=memory_layer,
        )
        rows = (
            await ai_memory_service.recall_memories(query)
            if mutate_recall
            else await ai_memory_service.retrieve_memories(query)
        )
        for row in rows:
            if row.memory_id in seen_ids:
                continue
            seen_ids.add(row.memory_id)
            rows_for_layer.append(row)
    return rows_for_layer


def _build_knowledge_targets(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> list[tuple["AIMemoryAnchorType", str]]:
    return [
        (anchor.anchor_type, anchor.anchor_id)
        for anchor in build_memory_anchors(identity, user_id)
    ]


async def store_extracted_memories(
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    message_text: str,
    source_message_id: str | None,
) -> AIMemoryExtractionResult:
    """Extract and store structured long-term memory candidates.

    Returns the full extraction result including sentiment and name.
    """

    write_anchors = build_memory_write_anchors(identity, user_id)
    existing_memories: list[AIMemoryDefinition] = []
    seen_memory_ids: set[str] = set()
    for anchor in write_anchors:
        rows = await ai_memory_service.list_memories(
            anchor_type=anchor.anchor_type,
            anchor_id=anchor.anchor_id,
            memory_layer="long_term",
        )
        for row in rows:
            if row.memory_id in seen_memory_ids:
                continue
            seen_memory_ids.add(row.memory_id)
            existing_memories.append(row)

    extraction_result = await extract_memory_from_message(
        message_text=message_text,
        existing_memories=tuple(existing_memories),
    )
    candidates = extraction_result.candidates
    await ingest_profile_from_message(
        identity=identity,
        user_id=user_id,
        self_introduction_name=extraction_result.self_introduction_name,
    )
    if candidates:
        candidates_by_anchor: dict[
            AIMemoryWriteAnchor,
            list[AIMemoryExtractionCandidate],
        ] = {}
        for candidate in candidates:
            anchor = select_memory_write_anchor(
                identity=identity,
                candidate=candidate,
                write_anchors=write_anchors,
            )
            if anchor is None:
                continue
            candidates_by_anchor.setdefault(anchor, []).append(candidate)

        for anchor, scoped_candidates in candidates_by_anchor.items():
            await ai_memory_service.remember_candidates(
                anchor_type=anchor.anchor_type,
                anchor_id=anchor.anchor_id,
                source_message_id=source_message_id,
                candidates=scoped_candidates,
                scene_type=identity.scene_type,
            )
            await ai_memory_service.consolidate_anchor_summary(
                anchor_type=anchor.anchor_type,
                anchor_id=anchor.anchor_id,
            )

    return extraction_result
