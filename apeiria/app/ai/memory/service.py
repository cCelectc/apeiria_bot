"""Memory CRUD and retrieval service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select, update

from apeiria.app.ai.memory.actions import build_memory_write_plans
from apeiria.app.ai.memory.embeddings import (
    EMBEDDING_MODEL_NAME,
    cosine_similarity,
    embed_text,
)
from apeiria.app.ai.memory.models import (
    AIMemoryAnchorType,
    AIMemoryDefinition,
    AIMemoryExtractionCandidate,
    AIMemoryKind,
    AIMemoryLayer,
    AIMemoryQuery,
)
from apeiria.app.ai.memory.ranking import rank_memory_items
from apeiria.app.ai.memory.summary import build_summary_memory_content
from apeiria.app.ai.model.service import ai_model_facade
from apeiria.app.ai.model.source_service import ai_source_service
from apeiria.infra.db.models import AIMemoryEmbedding, AIMemoryItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIMemoryCreateInput:
    """Create payload for one structured memory item."""

    anchor_type: AIMemoryAnchorType
    anchor_id: str
    memory_layer: AIMemoryLayer
    memory_kind: AIMemoryKind
    content: str
    is_editable: bool = True
    is_ignored: bool = False
    source_turn_id: str | None = None
    salience: float = 0.5
    confidence: float = 0.5


@dataclass(frozen=True)
class AIMemoryUpdateInput:
    """Update payload for one existing memory item."""

    content: str
    salience: float
    confidence: float
    source_turn_id: str | None


class AIMemoryService:
    """Long-term memory CRUD and retrieval service."""

    SUMMARY_MEMORY_LAYER: AIMemoryLayer = "summary"
    SUMMARY_MEMORY_KIND: AIMemoryKind = "note"
    KNOWLEDGE_RERANK_CANDIDATE_MULTIPLIER = 4
    KNOWLEDGE_RERANK_MIN_CANDIDATES = 8

    async def create_memory(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem:
        """Create one structured memory item."""

        memory = AIMemoryItem(
            memory_id=f"mem_{uuid4().hex}",
            anchor_type=create_input.anchor_type,
            anchor_id=create_input.anchor_id,
            memory_layer=create_input.memory_layer,
            memory_kind=create_input.memory_kind,
            content=create_input.content,
            is_editable=create_input.is_editable,
            is_ignored=create_input.is_ignored,
            source_turn_id=create_input.source_turn_id,
            salience=create_input.salience,
            confidence=create_input.confidence,
        )
        session.add(memory)
        await session.flush()
        return memory

    async def create_memory_if_absent(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem | None:
        """Create one memory item only when an identical item does not exist."""

        result = await session.execute(
            select(AIMemoryItem).where(
                AIMemoryItem.anchor_type == create_input.anchor_type,
                AIMemoryItem.anchor_id == create_input.anchor_id,
                AIMemoryItem.memory_layer == create_input.memory_layer,
                AIMemoryItem.memory_kind == create_input.memory_kind,
                AIMemoryItem.content == create_input.content,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return None
        return await self.create_memory(session, create_input)

    async def get_memory_by_identity(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem | None:
        """Load one exact memory row for the given identity tuple."""

        result = await session.execute(
            select(AIMemoryItem).where(
                AIMemoryItem.anchor_type == create_input.anchor_type,
                AIMemoryItem.anchor_id == create_input.anchor_id,
                AIMemoryItem.memory_layer == create_input.memory_layer,
                AIMemoryItem.memory_kind == create_input.memory_kind,
                AIMemoryItem.content == create_input.content,
            )
        )
        return result.scalar_one_or_none()

    async def get_memory(
        self,
        session: AsyncSession,
        *,
        memory_id: str,
    ) -> AIMemoryItem | None:
        """Load one memory row by stable id."""

        result = await session.execute(
            select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
        )
        return result.scalar_one_or_none()

    async def update_memory_content(
        self,
        session: AsyncSession,
        *,
        memory_id: str,
        update_input: AIMemoryUpdateInput,
    ) -> AIMemoryItem | None:
        """Update one existing memory item in place."""

        row = await self.get_memory(session, memory_id=memory_id)
        if row is None:
            return None
        row.content = update_input.content
        row.salience = update_input.salience
        row.confidence = update_input.confidence
        row.source_turn_id = update_input.source_turn_id
        await session.flush()
        return row

    async def remember_candidates(
        self,
        session: AsyncSession,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        source_turn_id: str | None,
        candidates: list[AIMemoryExtractionCandidate],
    ) -> list[AIMemoryItem]:
        """Persist extracted long-term memory candidates while avoiding duplicates."""

        existing_memories = await self.list_memories(
            session,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            memory_layer="long_term",
        )
        plans = build_memory_write_plans(existing_memories, candidates)
        created: list[AIMemoryItem] = []
        for plan in plans:
            candidate = plan.candidate
            if plan.action == "update" and plan.target_memory_id is not None:
                row = await self.update_memory_content(
                    session,
                    memory_id=plan.target_memory_id,
                    update_input=AIMemoryUpdateInput(
                        content=candidate.content,
                        salience=candidate.salience,
                        confidence=candidate.confidence,
                        source_turn_id=source_turn_id,
                    ),
                )
                if row is not None:
                    created.append(row)
                continue
            row = await self.create_memory_if_absent(
                session,
                AIMemoryCreateInput(
                    anchor_type=anchor_type,
                    anchor_id=anchor_id,
                    memory_layer="long_term",
                    memory_kind=candidate.memory_kind,
                    content=candidate.content,
                    is_editable=True,
                    source_turn_id=source_turn_id,
                    salience=candidate.salience,
                    confidence=candidate.confidence,
                ),
            )
            if row is not None:
                created.append(row)
        return created

    async def list_memories(  # noqa: PLR0913
        self,
        session: AsyncSession,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
        memory_layer: AIMemoryLayer | None = None,
        memory_kind: AIMemoryKind | None = None,
        include_ignored: bool = False,
    ) -> list[AIMemoryDefinition]:
        """List all memories for one anchor boundary."""

        query = select(AIMemoryItem).where(
            AIMemoryItem.anchor_type == anchor_type,
            AIMemoryItem.anchor_id == anchor_id,
        )
        if memory_layer is not None:
            query = query.where(AIMemoryItem.memory_layer == memory_layer)
        if memory_kind is not None:
            query = query.where(AIMemoryItem.memory_kind == memory_kind)
        if not include_ignored:
            query = query.where(AIMemoryItem.is_ignored.is_(False))
        result = await session.execute(
            query.order_by(AIMemoryItem.created_at.asc(), AIMemoryItem.id.asc())
        )
        return [self._to_definition(row) for row in result.scalars().all()]

    async def retrieve_memories(
        self,
        session: AsyncSession,
        query: AIMemoryQuery,
    ) -> list[AIMemoryDefinition]:
        """Retrieve relevance-ranked memories for one query."""

        memories = await self.list_memories(
            session,
            anchor_type=query.anchor_type,
            anchor_id=query.anchor_id,
            memory_layer=query.memory_layer,
            memory_kind=query.memory_kind,
        )
        return rank_memory_items(memories, query)

    async def create_knowledge_memory(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem:
        """Create one knowledge memory and persist its embedding."""

        memory = await self.create_memory_if_absent(session, create_input)
        if memory is None:
            existing = await self.get_memory_by_identity(session, create_input)
            assert existing is not None
            memory = existing
        await self.upsert_memory_embedding(
            session,
            memory_id=memory.memory_id,
            content=memory.content,
        )
        return memory

    async def upsert_memory_embedding(
        self,
        session: AsyncSession,
        *,
        memory_id: str,
        content: str,
    ) -> AIMemoryEmbedding:
        """Create or update one stored memory embedding."""

        result = await session.execute(
            select(AIMemoryEmbedding).where(AIMemoryEmbedding.memory_id == memory_id)
        )
        row = result.scalar_one_or_none()
        embedding_model, vector = await self._build_knowledge_embedding_vector(
            session,
            content=content,
        )
        vector_json = json.dumps(vector)
        if row is None:
            row = AIMemoryEmbedding(
                memory_id=memory_id,
                embedding_model=embedding_model,
                vector_json=vector_json,
            )
            session.add(row)
        else:
            row.embedding_model = embedding_model
            row.vector_json = vector_json
        await session.flush()
        return row

    async def retrieve_knowledge_memories(
        self,
        session: AsyncSession,
        *,
        targets: list[tuple[AIMemoryAnchorType, str]],
        query_text: str,
        limit: int,
    ) -> list[AIMemoryDefinition]:
        """Retrieve top-k knowledge memories through local embedding similarity."""

        if limit <= 0 or not query_text.strip():
            return []

        query_embedding_model, query_vector = (
            await self._build_knowledge_embedding_vector(
                session,
                content=query_text,
            )
        )
        scored: list[tuple[float, AIMemoryDefinition]] = []
        seen_memory_ids: set[str] = set()

        for anchor_type, anchor_id in targets:
            memories = await self.list_memories(
                session,
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                memory_layer="knowledge",
            )
            for memory in memories:
                if memory.memory_id in seen_memory_ids:
                    continue
                seen_memory_ids.add(memory.memory_id)
                result = await session.execute(
                    select(AIMemoryEmbedding).where(
                        AIMemoryEmbedding.memory_id == memory.memory_id
                    )
                )
                embedding_row = result.scalar_one_or_none()
                if (
                    embedding_row is None
                    or embedding_row.embedding_model != query_embedding_model
                ):
                    embedding_row = await self.upsert_memory_embedding(
                        session,
                        memory_id=memory.memory_id,
                        content=memory.content,
                    )
                try:
                    memory_vector = json.loads(embedding_row.vector_json)
                except json.JSONDecodeError:
                    continue
                if not isinstance(memory_vector, list):
                    continue
                numeric_vector = [
                    float(value)
                    for value in memory_vector
                    if isinstance(value, (int, float))
                ]
                if not numeric_vector:
                    continue
                scored.append((cosine_similarity(query_vector, numeric_vector), memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        dense_ranked = [memory for _, memory in scored]
        return await self._rerank_knowledge_memories(
            session,
            query_text=query_text,
            memories=dense_ranked,
            limit=limit,
        )

    async def _build_knowledge_embedding_vector(
        self,
        session: "AsyncSession",
        *,
        content: str,
    ) -> tuple[str, list[float]]:
        selected = await ai_model_facade.select_capability_model(
            session,
            capability_type="embedding",
        )
        if selected is None:
            return EMBEDDING_MODEL_NAME, embed_text(content)

        try:
            api_key = ai_source_service.get_source_api_key(selected.source)
            if not api_key:
                return EMBEDDING_MODEL_NAME, embed_text(content)
            response = await ai_model_facade.embed_texts_for_source(
                source=selected.source,
                api_key=api_key,
                model_name=selected.model.model_identifier,
                texts=(content,),
            )
        except Exception:  # noqa: BLE001
            return EMBEDDING_MODEL_NAME, embed_text(content)

        if not response.vectors:
            return EMBEDDING_MODEL_NAME, embed_text(content)

        return selected.model.model_id, list(response.vectors[0])

    async def _rerank_knowledge_memories(  # noqa: PLR0911
        self,
        session: "AsyncSession",
        *,
        query_text: str,
        memories: list[AIMemoryDefinition],
        limit: int,
    ) -> list[AIMemoryDefinition]:
        if limit <= 0 or not memories:
            return []

        selected = await ai_model_facade.select_capability_model(
            session,
            capability_type="rerank",
        )
        if selected is None:
            return memories[:limit]

        api_key = ai_source_service.get_source_api_key(selected.source)
        if not api_key:
            return memories[:limit]

        candidate_limit = min(
            len(memories),
            max(
                limit * self.KNOWLEDGE_RERANK_CANDIDATE_MULTIPLIER,
                self.KNOWLEDGE_RERANK_MIN_CANDIDATES,
            ),
        )
        candidates = memories[:candidate_limit]
        try:
            response = await ai_model_facade.rerank_documents_for_source(
                source=selected.source,
                api_key=api_key,
                model_name=selected.model.model_identifier,
                query=query_text,
                documents=tuple(memory.content for memory in candidates),
                top_n=min(limit, len(candidates)),
            )
        except Exception:  # noqa: BLE001
            return memories[:limit]

        reranked: list[AIMemoryDefinition] = []
        seen_indexes: set[int] = set()
        for item in response.results:
            if item.index < 0 or item.index >= len(candidates):
                continue
            if item.index in seen_indexes:
                continue
            seen_indexes.add(item.index)
            reranked.append(candidates[item.index])
            if len(reranked) >= limit:
                return reranked

        if reranked:
            dense_fallback = [
                memory
                for index, memory in enumerate(candidates)
                if index not in seen_indexes
            ]
            return (reranked + dense_fallback)[:limit]

        return memories[:limit]

    async def recall_memories(
        self,
        session: AsyncSession,
        query: AIMemoryQuery,
    ) -> list[AIMemoryDefinition]:
        """Retrieve memories for live AI use and stamp recall time."""

        recalled = await self.retrieve_memories(session, query)
        if not recalled:
            return []

        recalled_at = datetime.now(timezone.utc)
        await self._mark_memories_recalled(
            session,
            memory_ids=[memory.memory_id for memory in recalled],
            recalled_at=recalled_at,
        )
        return [
            AIMemoryDefinition(
                memory_id=memory.memory_id,
                anchor_type=memory.anchor_type,
                anchor_id=memory.anchor_id,
                memory_layer=memory.memory_layer,
                memory_kind=memory.memory_kind,
                content=memory.content,
                is_editable=memory.is_editable,
                is_ignored=memory.is_ignored,
                source_turn_id=memory.source_turn_id,
                salience=memory.salience,
                confidence=memory.confidence,
                last_recalled_at=recalled_at,
                created_at=memory.created_at,
            )
            for memory in recalled
        ]

    async def delete_memory(
        self,
        session: AsyncSession,
        *,
        memory_id: str,
    ) -> bool:
        """Delete one memory item by stable id."""

        memory = await self.get_memory(session, memory_id=memory_id)
        if memory is None:
            return False
        result = await session.execute(
            select(AIMemoryEmbedding).where(AIMemoryEmbedding.memory_id == memory_id)
        )
        embedding = result.scalar_one_or_none()
        if embedding is not None:
            await session.delete(embedding)
        await session.delete(memory)
        return True

    async def consolidate_anchor_summary(
        self,
        session: AsyncSession,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
    ) -> None:
        """Build or refresh one deterministic summary memory for the anchor."""

        memories = await self.list_memories(
            session,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            include_ignored=True,
        )
        summary_content = build_summary_memory_content(memories)
        existing_summary = next(
            (
                memory
                for memory in memories
                if memory.memory_layer == self.SUMMARY_MEMORY_LAYER
            ),
            None,
        )

        if summary_content is None:
            if existing_summary is not None:
                await self.delete_memory(session, memory_id=existing_summary.memory_id)
            return

        if existing_summary is not None:
            if existing_summary.content == summary_content:
                return
            await self.update_memory_content(
                session,
                memory_id=existing_summary.memory_id,
                update_input=AIMemoryUpdateInput(
                    content=summary_content,
                    salience=0.8,
                    confidence=0.85,
                    source_turn_id=existing_summary.source_turn_id,
                ),
            )
            return

        await self.create_memory(
            session,
            AIMemoryCreateInput(
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                memory_layer=self.SUMMARY_MEMORY_LAYER,
                memory_kind=self.SUMMARY_MEMORY_KIND,
                content=summary_content,
                is_editable=False,
                salience=0.8,
                confidence=0.85,
            ),
        )

    async def _mark_memories_recalled(
        self,
        session: AsyncSession,
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        if not memory_ids:
            return

        await session.execute(
            update(AIMemoryItem)
            .where(AIMemoryItem.memory_id.in_(memory_ids))
            .values(last_recalled_at=recalled_at.replace(tzinfo=None))
        )
        await session.flush()

    @staticmethod
    def _to_definition(row: AIMemoryItem) -> AIMemoryDefinition:
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        last_recalled_at = None
        if row.last_recalled_at is not None:
            last_recalled_at = (
                row.last_recalled_at.replace(tzinfo=timezone.utc)
                if row.last_recalled_at.tzinfo is None
                else row.last_recalled_at
            )
        return AIMemoryDefinition(
            memory_id=row.memory_id,
            anchor_type=cast("AIMemoryAnchorType", row.anchor_type),
            anchor_id=row.anchor_id,
            memory_layer=cast("AIMemoryLayer", row.memory_layer),
            memory_kind=cast("AIMemoryKind", row.memory_kind),
            content=row.content,
            is_editable=row.is_editable,
            is_ignored=row.is_ignored,
            source_turn_id=row.source_turn_id,
            salience=row.salience,
            confidence=row.confidence,
            last_recalled_at=last_recalled_at,
            created_at=created_at,
        )


ai_memory_service = AIMemoryService()
