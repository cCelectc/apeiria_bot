"""Memory CRUD and retrieval service."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from apeiria.ai.memory.actions import build_memory_write_plans
from apeiria.ai.memory.contracts import AIMemoryCreateInput, AIMemoryUpdateInput
from apeiria.ai.memory.knowledge import KnowledgeMemoryCoordinator
from apeiria.ai.memory.ranking import rank_memory_items
from apeiria.ai.memory.repository import AIMemoryRepository, utcnow
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
        """Create one structured memory item."""

        memory = self._repository.create_memory(
            create_input,
            ignore_existing=False,
        )
        assert memory is not None
        return memory

    async def create_memory_if_absent(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        """Create one memory item only when an identical item does not exist."""

        return self._repository.create_memory(
            create_input,
            ignore_existing=True,
        )

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
    ) -> AIMemoryDefinition | None:
        """Update one existing memory item in place."""

        return self._repository.update_memory_content(
            memory_id=memory_id,
            update_input=update_input,
        )

    async def remember_candidates(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        source_message_id: str | None,
        candidates: list[AIMemoryExtractionCandidate],
    ) -> list[AIMemoryDefinition]:
        """Persist extracted long-term memory candidates while avoiding duplicates."""

        existing_memories = await self.list_memories(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            memory_layer="long_term",
        )
        plans = build_memory_write_plans(existing_memories, candidates)
        created: list[AIMemoryDefinition] = []
        for plan in plans:
            candidate = plan.candidate
            if plan.action == "update" and plan.target_memory_id is not None:
                row = await self.update_memory_content(
                    memory_id=plan.target_memory_id,
                    update_input=AIMemoryUpdateInput(
                        content=candidate.content,
                        salience=candidate.salience,
                        confidence=candidate.confidence,
                        source_message_id=source_message_id,
                    ),
                )
                if row is not None:
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
        include_ignored: bool = False,
    ) -> list[AIMemoryDefinition]:
        """List all memories for one anchor boundary."""

        return self._repository.list_memories(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            memory_layer=memory_layer,
            memory_kind=memory_kind,
            include_ignored=include_ignored,
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
        await self._mark_memories_recalled(
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
        return self._repository.delete_memory(memory_id=memory_id)

    async def toggle_memory_ignored(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        """Toggle the is_ignored flag on one memory item."""

        return self._repository.toggle_memory_ignored(memory_id=memory_id)

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

    async def bulk_set_ignored(
        self,
        *,
        memory_ids: list[str],
        ignored: bool,
    ) -> int:
        """Set is_ignored on multiple memories. Returns count updated."""

        return self._repository.bulk_set_ignored(
            memory_ids=memory_ids,
            ignored=ignored,
        )

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

    async def _mark_memories_recalled(
        self,
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        self._repository.mark_memories_recalled(
            memory_ids=memory_ids,
            recalled_at=recalled_at,
        )


ai_memory_service = AIMemoryService()
