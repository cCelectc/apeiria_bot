"""Memory CRUD and retrieval service."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, cast

from apeiria.ai.memory.actions import build_memory_write_plans
from apeiria.ai.memory.contracts import (
    AIMemoryCreateInput,
    AIMemoryStateUpdateInput,
    AIMemoryUpdateInput,
)
from apeiria.ai.memory.governance import (
    default_use_mode_for_manual_memory,
    govern_extracted_memory,
)
from apeiria.ai.memory.knowledge import KnowledgeMemoryCoordinator
from apeiria.ai.memory.models import (
    AIMemoryBeliefAction,
    AIMemoryRetrievalDiagnostics,
    AIMemoryRetrievalSelection,
    AIMemoryUseMode,
)
from apeiria.ai.memory.ranking import rank_memory_items
from apeiria.ai.memory.repository import (
    AIMemoryActorType,
    AIMemoryRepository,
    utcnow,
)
from apeiria.ai.memory.summaries import MemorySummaryCoordinator

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory.embedding_store import AIMemoryEmbeddingRecord
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryExtractionCandidate,
        AIMemoryKind,
        AIMemoryLayer,
        AIMemoryLifecycleState,
        AIMemoryQuery,
    )


class AIMemoryService:
    """Long-term memory CRUD and retrieval service."""

    SUMMARY_MEMORY_LAYER: AIMemoryLayer = MemorySummaryCoordinator.SUMMARY_MEMORY_LAYER
    SUMMARY_MEMORY_KIND: AIMemoryKind = MemorySummaryCoordinator.SUMMARY_MEMORY_KIND
    KNOWLEDGE_RERANK_CANDIDATE_MULTIPLIER = (
        KnowledgeMemoryCoordinator.RERANK_CANDIDATE_MULTIPLIER
    )
    KNOWLEDGE_RERANK_MIN_CANDIDATES = KnowledgeMemoryCoordinator.RERANK_MIN_CANDIDATES

    def __init__(
        self,
        *,
        repository: AIMemoryRepository | None = None,
        knowledge: KnowledgeMemoryCoordinator | None = None,
        summaries: MemorySummaryCoordinator | None = None,
    ) -> None:
        self._repository = repository or AIMemoryRepository()
        self._knowledge = knowledge or KnowledgeMemoryCoordinator(self._repository)
        self._summaries = summaries or MemorySummaryCoordinator(self._repository)

    async def create_memory(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition:
        """Create one governed memory item."""

        governed_input = _with_default_governance(create_input)
        memory = self._repository.create_memory(
            governed_input,
            ignore_existing=False,
        )
        assert memory is not None
        self._repository.record_belief_action(
            memory_id=memory.memory_id,
            action=_creation_action_for_state(memory.lifecycle_state),
            actor_type=_actor_for_memory(memory),
            reason=memory.governance_reason,
            source_message_id=memory.source_message_id,
            next_state=memory.lifecycle_state,
        )
        return memory

    async def create_memory_if_absent(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        """Create one memory item only when an identical item does not exist."""

        governed_input = _with_default_governance(create_input)
        memory = self._repository.create_memory(
            governed_input,
            ignore_existing=True,
        )
        if memory is not None:
            self._repository.record_belief_action(
                memory_id=memory.memory_id,
                action=_creation_action_for_state(memory.lifecycle_state),
                actor_type=_actor_for_memory(memory),
                reason=memory.governance_reason,
                source_message_id=memory.source_message_id,
                next_state=memory.lifecycle_state,
            )
        return memory

    async def get_memory_by_identity(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        """Load one exact memory row for the given identity tuple."""

        return self._repository.get_memory_by_identity(create_input)

    async def get_memory(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        """Load one memory row by stable id."""

        return self._repository.get_memory(memory_id=memory_id)

    async def update_memory_content(
        self,
        *,
        memory_id: str,
        update_input: AIMemoryUpdateInput,
        record_action: bool = True,
    ) -> AIMemoryDefinition | None:
        """Update one existing memory item in place."""

        existing = await self.get_memory(memory_id=memory_id)
        row = self._repository.update_memory_content(
            memory_id=memory_id,
            update_input=update_input,
        )
        if row is not None and record_action:
            self._repository.record_belief_action(
                memory_id=memory_id,
                action="revise",
                actor_type=_actor_for_memory(row),
                reason="memory content revised",
                source_message_id=update_input.source_message_id,
                previous_state=(
                    existing.lifecycle_state if existing is not None else None
                ),
                next_state=row.lifecycle_state,
            )
        return row

    async def remember_candidates(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        source_message_id: str | None,
        candidates: list[AIMemoryExtractionCandidate],
        scene_type: str = "private",
    ) -> list[AIMemoryDefinition]:
        """Persist extracted long-term memory candidates while avoiding duplicates."""

        existing_memories = await self.list_memories(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            memory_layer="long_term",
            lifecycle_states=("active", "candidate"),
        )
        plans = build_memory_write_plans(existing_memories, candidates)
        created: list[AIMemoryDefinition] = []
        for plan in plans:
            candidate = plan.candidate
            decision = govern_extracted_memory(candidate, scene_type=scene_type)
            if decision.lifecycle_state is None:
                self._repository.record_belief_action(
                    memory_id=None,
                    action="reject",
                    actor_type="system",
                    reason=decision.reason,
                    source_message_id=source_message_id,
                    next_state=None,
                )
                continue
            if decision.target_scope != anchor_type:
                self._repository.record_belief_action(
                    memory_id=None,
                    action="reject",
                    actor_type="system",
                    reason=(
                        "candidate target scope "
                        f"{decision.target_scope} does not match write scope "
                        f"{anchor_type}"
                    ),
                    source_message_id=source_message_id,
                    next_state=None,
                )
                continue
            if plan.action == "update" and plan.target_memory_id is not None:
                existing = await self.get_memory(memory_id=plan.target_memory_id)
                row = await self.update_memory_content(
                    memory_id=plan.target_memory_id,
                    update_input=AIMemoryUpdateInput(
                        content=candidate.content,
                        salience=candidate.salience,
                        confidence=candidate.confidence,
                        source_message_id=source_message_id,
                    ),
                    record_action=False,
                )
                if row is not None:
                    updated = await self.set_memory_state(
                        memory_id=row.memory_id,
                        lifecycle_state=decision.lifecycle_state,
                        default_use_mode=decision.use_mode,
                        governance_reason=decision.reason,
                        action="revise",
                        actor_type="system",
                        source_message_id=source_message_id,
                        previous_state=(
                            existing.lifecycle_state if existing is not None else None
                        ),
                    )
                    row = updated or row
                    created.append(row)
                continue
            row = await self.create_memory_if_absent(
                AIMemoryCreateInput(
                    anchor_type=anchor_type,
                    anchor_id=anchor_id,
                    memory_layer="long_term",
                    memory_kind=candidate.memory_kind,
                    content=candidate.content,
                    is_editable=True,
                    lifecycle_state=decision.lifecycle_state,
                    default_use_mode=decision.use_mode,
                    governance_reason=decision.reason,
                    source_message_id=source_message_id,
                    salience=candidate.salience,
                    confidence=candidate.confidence,
                ),
            )
            if row is not None:
                created.append(row)
        return created

    async def list_memories(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        memory_layer: AIMemoryLayer | None = None,
        memory_kind: AIMemoryKind | None = None,
        lifecycle_states: tuple[AIMemoryLifecycleState, ...] = ("active",),
    ) -> list[AIMemoryDefinition]:
        """List all memories for one anchor boundary."""

        return self._repository.list_memories(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            memory_layer=memory_layer,
            memory_kind=memory_kind,
            lifecycle_states=lifecycle_states,
        )

    async def retrieve_memories(
        self,
        query: AIMemoryQuery,
    ) -> list[AIMemoryDefinition]:
        """Retrieve relevance-ranked memories for one query."""

        memories = await self.list_memories(
            anchor_type=query.anchor_type,
            anchor_id=query.anchor_id,
            memory_layer=query.memory_layer,
            memory_kind=query.memory_kind,
        )
        return rank_memory_items(memories, query)

    async def retrieve_memory_selections(
        self,
        query: AIMemoryQuery,
    ) -> AIMemoryRetrievalDiagnostics:
        """Retrieve active memories with use-mode diagnostics for one query."""

        active = await self.list_memories(
            anchor_type=query.anchor_type,
            anchor_id=query.anchor_id,
            memory_layer=query.memory_layer,
            memory_kind=query.memory_kind,
            lifecycle_states=("active",),
        )
        inactive = await self.list_memories(
            anchor_type=query.anchor_type,
            anchor_id=query.anchor_id,
            memory_layer=query.memory_layer,
            memory_kind=query.memory_kind,
            lifecycle_states=("candidate", "suppressed", "archived"),
        )
        selected = tuple(
            AIMemoryRetrievalSelection(
                memory=memory,
                use_mode=memory.default_use_mode,
                scope_rank=0,
            )
            for memory in rank_memory_items(active, query)
            if memory.default_use_mode != "ignore"
        )
        excluded = tuple(
            AIMemoryRetrievalSelection(
                memory=memory,
                use_mode="ignore",
                scope_rank=0,
                exclusion_reason=f"lifecycle_state:{memory.lifecycle_state}",
            )
            for memory in inactive[: query.limit]
        )
        return AIMemoryRetrievalDiagnostics(selected=selected, excluded=excluded)

    async def create_knowledge_memory(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition:
        """Create one knowledge memory and persist its embedding."""

        return await self._knowledge.create_knowledge_memory(create_input)

    async def upsert_memory_embedding(
        self,
        *,
        memory_id: str,
        content: str,
    ) -> "AIMemoryEmbeddingRecord":
        """Create or update one file-backed memory embedding."""

        return await self._knowledge.upsert_memory_embedding(
            memory_id=memory_id,
            content=content,
        )

    async def retrieve_knowledge_memories(
        self,
        *,
        targets: list[tuple[AIMemoryAnchorType, str]],
        query_text: str,
        limit: int,
    ) -> list[AIMemoryDefinition]:
        """Retrieve top-k knowledge memories through local embedding similarity."""

        return await self._knowledge.retrieve_knowledge_memories(
            targets=targets,
            query_text=query_text,
            limit=limit,
        )

    async def recall_memories(
        self,
        query: AIMemoryQuery,
    ) -> list[AIMemoryDefinition]:
        """Retrieve memories for live AI use and stamp recall time."""

        recalled = await self.retrieve_memories(query)
        if not recalled:
            return []

        recalled_at = utcnow()
        await self.mark_memories_recalled(
            memory_ids=[memory.memory_id for memory in recalled],
            recalled_at=recalled_at,
        )
        return [replace(memory, last_recalled_at=recalled_at) for memory in recalled]

    async def delete_memory(
        self,
        *,
        memory_id: str,
    ) -> bool:
        """Delete one memory item by stable id."""

        memory = self._repository.get_memory(memory_id=memory_id)
        if memory is None:
            return False
        self._knowledge.delete_memory_embedding(memory_id=memory_id)
        deleted = self._repository.delete_memory(memory_id=memory_id)
        if deleted:
            self._repository.record_belief_action(
                memory_id=None,
                action="delete",
                actor_type=_actor_for_memory(memory),
                reason=f"deleted memory {memory_id}",
                source_message_id=memory.source_message_id,
                previous_state=memory.lifecycle_state,
                next_state=None,
            )
        return deleted

    async def set_memory_state(  # noqa: PLR0913
        self,
        *,
        memory_id: str,
        lifecycle_state: AIMemoryLifecycleState,
        default_use_mode: AIMemoryUseMode | None = None,
        governance_reason: str | None = None,
        action: AIMemoryBeliefAction | None = None,
        actor_type: AIMemoryActorType = "operator",
        source_message_id: str | None = None,
        previous_state: AIMemoryLifecycleState | None = None,
    ) -> AIMemoryDefinition | None:
        """Set lifecycle state for one governed memory belief."""

        existing = await self.get_memory(memory_id=memory_id)
        row = self._repository.set_memory_state(
            memory_id=memory_id,
            update_input=AIMemoryStateUpdateInput(
                lifecycle_state=lifecycle_state,
                default_use_mode=default_use_mode,
                governance_reason=governance_reason,
            ),
        )
        if row is not None:
            self._repository.record_belief_action(
                memory_id=memory_id,
                action=action or _action_for_state(lifecycle_state),
                actor_type=actor_type,
                reason=governance_reason,
                source_message_id=source_message_id,
                previous_state=previous_state
                or (existing.lifecycle_state if existing is not None else None),
                next_state=lifecycle_state,
            )
        return row

    async def bulk_delete_memories(
        self,
        *,
        memory_ids: list[str],
    ) -> int:
        """Delete multiple memory items by stable id. Returns count deleted."""

        deleted = 0
        for memory_id in memory_ids:
            if await self.delete_memory(memory_id=memory_id):
                deleted += 1
        return deleted

    async def bulk_set_memory_state(
        self,
        *,
        memory_ids: list[str],
        lifecycle_state: AIMemoryLifecycleState,
        default_use_mode: AIMemoryUseMode | None = None,
        governance_reason: str | None = None,
    ) -> int:
        """Set lifecycle state on multiple memories. Returns count updated."""

        existing = {
            memory_id: memory
            for memory_id in memory_ids
            if (memory := await self.get_memory(memory_id=memory_id)) is not None
        }
        count = self._repository.bulk_set_memory_state(
            memory_ids=memory_ids,
            update_input=AIMemoryStateUpdateInput(
                lifecycle_state=lifecycle_state,
                default_use_mode=default_use_mode,
                governance_reason=governance_reason,
            ),
        )
        for memory_id, memory in existing.items():
            self._repository.record_belief_action(
                memory_id=memory_id,
                action=_action_for_state(lifecycle_state),
                actor_type="operator",
                reason=governance_reason,
                previous_state=memory.lifecycle_state,
                next_state=lifecycle_state,
            )
        return count

    async def consolidate_anchor_summary(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
    ) -> None:
        """Build or refresh one deterministic summary memory for the anchor."""

        await self._summaries.consolidate_anchor_summary(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
        )

    async def mark_memories_recalled(
        self,
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        """Stamp recall timestamps for selected memories."""

        self._repository.mark_memories_recalled(
            memory_ids=memory_ids,
            recalled_at=recalled_at,
        )


ai_memory_service = AIMemoryService()


def _with_default_governance(create_input: AIMemoryCreateInput) -> AIMemoryCreateInput:
    if create_input.default_use_mode != "context" or create_input.governance_reason:
        return create_input
    return AIMemoryCreateInput(
        anchor_type=create_input.anchor_type,
        anchor_id=create_input.anchor_id,
        memory_layer=create_input.memory_layer,
        memory_kind=create_input.memory_kind,
        content=create_input.content,
        is_editable=create_input.is_editable,
        lifecycle_state=create_input.lifecycle_state,
        default_use_mode=cast(
            "AIMemoryUseMode",
            default_use_mode_for_manual_memory(create_input.memory_kind),
        ),
        governance_reason="manual governed memory write",
        source_message_id=create_input.source_message_id,
        salience=create_input.salience,
        confidence=create_input.confidence,
    )


def _action_for_state(state: AIMemoryLifecycleState) -> AIMemoryBeliefAction:
    if state == "active":
        return "activate"
    if state == "suppressed":
        return "suppress"
    if state == "archived":
        return "archive"
    return "revise"


def _creation_action_for_state(
    state: AIMemoryLifecycleState,
) -> AIMemoryBeliefAction:
    if state in {"active", "candidate"}:
        return "accept"
    if state == "suppressed":
        return "suppress"
    return "archive"


def _actor_for_memory(memory: AIMemoryDefinition) -> AIMemoryActorType:
    return "operator" if memory.memory_layer == "operator" else "system"
