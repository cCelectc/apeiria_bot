"""Runtime memory steps extracted from the orchestration compatibility layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.app.ai.conversation.identity import build_participant_subject_id
from apeiria.app.ai.memory.extraction import (
    build_memory_extraction_prompt,
    parse_memory_extraction_response,
)
from apeiria.app.ai.memory.models import AIMemoryLayer, AIMemoryQuery
from apeiria.app.ai.memory.service import ai_memory_service
from apeiria.app.ai.model.models import AIModelRouteQuery
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.person import ai_person_profile_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ChatSessionIdentity
    from apeiria.app.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryExtractionCandidate,
    )


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
) -> list[AIMemoryWriteAnchor]:
    """Build persistent storage anchors for extracted long-term memory."""

    return [
        AIMemoryWriteAnchor(anchor_type=anchor.anchor_type, anchor_id=anchor.anchor_id)
        for anchor in build_memory_anchors(identity, user_id)
    ]


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
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Recall memories for the current runtime turn."""

    recalled: list[AIMemoryDefinition] = []
    seen_ids: set[str] = set()

    for memory_layer in _RECALL_LAYER_ORDER:
        if memory_layer == "knowledge":
            layer_rows = await ai_memory_service.retrieve_knowledge_memories(
                session,
                targets=_build_knowledge_targets(identity, user_id),
                query_text=query_text,
                limit=_LAYER_RECALL_LIMITS[memory_layer],
            )
        else:
            layer_rows = await _collect_layer_memories(
                session,
                identity=identity,
                user_id=user_id,
                query_text=query_text,
                memory_layer=memory_layer,
                mutate_recall=True,
            )
        for memory in apply_memory_budget(
            [item for item in layer_rows if item.memory_id not in seen_ids],
            max_memories=_LAYER_RECALL_LIMITS[memory_layer],
        ):
            seen_ids.add(memory.memory_id)
            recalled.append(memory)

    return recalled


async def load_person_profile_for_prompt(
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
) -> tuple[str, ...]:
    """Load prompt-ready person profile lines for the active user."""

    profile = await ai_person_profile_service.build_prompt_profile(
        session,
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
    )
    if profile is None:
        return ()
    return profile.prompt_lines


async def retrieve_memories_for_preview(
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    query_text: str,
) -> list["AIMemoryDefinition"]:
    """Retrieve preview memories without mutating recall timestamps."""

    recalled: list[AIMemoryDefinition] = []
    seen_ids: set[str] = set()

    for memory_layer in _RECALL_LAYER_ORDER:
        if memory_layer == "knowledge":
            layer_rows = await ai_memory_service.retrieve_knowledge_memories(
                session,
                targets=_build_knowledge_targets(identity, user_id),
                query_text=query_text,
                limit=_LAYER_RECALL_LIMITS[memory_layer],
            )
        else:
            layer_rows = await _collect_layer_memories(
                session,
                identity=identity,
                user_id=user_id,
                query_text=query_text,
                memory_layer=memory_layer,
                mutate_recall=False,
            )
        for memory in apply_memory_budget(
            [item for item in layer_rows if item.memory_id not in seen_ids],
            max_memories=_LAYER_RECALL_LIMITS[memory_layer],
        ):
            seen_ids.add(memory.memory_id)
            recalled.append(memory)

    return recalled


async def _collect_layer_memories(  # noqa: PLR0913
    session: "AsyncSession",
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
            await ai_memory_service.recall_memories(session, query)
            if mutate_recall
            else await ai_memory_service.retrieve_memories(session, query)
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
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    user_id: str,
    message_text: str,
    source_message_id: str | None,
    ) -> None:
    """Extract and store structured long-term memory candidates."""

    write_anchors = build_memory_write_anchors(identity, user_id)
    existing_memories: list[AIMemoryDefinition] = []
    seen_memory_ids: set[str] = set()
    for anchor in write_anchors:
        rows = await ai_memory_service.list_memories(
            session,
            anchor_type=anchor.anchor_type,
            anchor_id=anchor.anchor_id,
            memory_layer="long_term",
        )
        for row in rows:
            if row.memory_id in seen_memory_ids:
                continue
            seen_memory_ids.add(row.memory_id)
            existing_memories.append(row)
    candidates: list[AIMemoryExtractionCandidate] = []
    selected = await ai_model_facade.select_model(
        session,
        query=AIModelRouteQuery(task_class="memory_extraction"),
    )
    if selected is not None:
        try:
            response = await ai_model_facade.generate_text(
                selected,
                prompt=build_memory_extraction_prompt(
                    message_text,
                    existing_memories=tuple(existing_memories),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=exc).warning("AI memory extraction failed")
            response = None
        if response is not None:
            candidates = parse_memory_extraction_response(response.content)

    await ai_person_profile_service.ingest_message(
        session,
        platform=identity.platform,
        user_id=identity.subject_id or user_id,
        message_text=message_text,
        source_message_id=source_message_id,
        candidates=tuple(candidates),
    )
    if not candidates:
        return

    for anchor in write_anchors:
        await ai_memory_service.remember_candidates(
            session,
            anchor_type=anchor.anchor_type,
            anchor_id=anchor.anchor_id,
            source_message_id=source_message_id,
            candidates=candidates,
        )
        await ai_memory_service.consolidate_anchor_summary(
            session,
            anchor_type=anchor.anchor_type,
            anchor_id=anchor.anchor_id,
        )
