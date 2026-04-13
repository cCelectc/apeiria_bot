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
    AIMemoryDefinition,
    AIMemoryDomain,
    AIMemoryExtractionCandidate,
    AIMemoryQuery,
    AIMemoryType,
)
from apeiria.app.ai.memory.ranking import rank_memory_items
from apeiria.app.ai.memory.summary import (
    SUMMARY_NOTE_PREFIX,
    build_summary_memory_content,
)
from apeiria.infra.db.models import AIMemoryEmbedding, AIMemoryItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIMemoryCreateInput:
    """Create payload for one structured memory item."""

    memory_type: AIMemoryType
    subject_type: str
    subject_id: str
    content: str
    memory_domain: AIMemoryDomain = "social"
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

    SUMMARY_MEMORY_TYPE: AIMemoryType = "note"

    async def create_memory(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem:
        """Create one structured memory item."""

        memory = AIMemoryItem(
            memory_id=f"mem_{uuid4().hex}",
            memory_domain=create_input.memory_domain,
            memory_type=create_input.memory_type,
            subject_type=create_input.subject_type,
            subject_id=create_input.subject_id,
            content=create_input.content,
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
                AIMemoryItem.memory_type == create_input.memory_type,
                AIMemoryItem.memory_domain == create_input.memory_domain,
                AIMemoryItem.subject_type == create_input.subject_type,
                AIMemoryItem.subject_id == create_input.subject_id,
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
                AIMemoryItem.memory_type == create_input.memory_type,
                AIMemoryItem.memory_domain == create_input.memory_domain,
                AIMemoryItem.subject_type == create_input.subject_type,
                AIMemoryItem.subject_id == create_input.subject_id,
                AIMemoryItem.content == create_input.content,
            )
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

        result = await session.execute(
            select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
        )
        row = result.scalar_one_or_none()
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
        subject_type: str,
        subject_id: str,
        source_turn_id: str | None,
        candidates: list[AIMemoryExtractionCandidate],
    ) -> list[AIMemoryItem]:
        """Persist extracted memory candidates while avoiding exact duplicates."""

        existing_memories = await self.list_memories(
            session,
            subject_type=subject_type,
            subject_id=subject_id,
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
                    memory_type=candidate.memory_type,
                    memory_domain="social",
                    subject_type=subject_type,
                    subject_id=subject_id,
                    content=candidate.content,
                    source_turn_id=source_turn_id,
                    salience=candidate.salience,
                    confidence=candidate.confidence,
                ),
            )
            if row is not None:
                created.append(row)
        return created

    async def list_memories(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_id: str,
        memory_domain: AIMemoryDomain | None = None,
    ) -> list[AIMemoryDefinition]:
        """List all memories for one subject boundary."""

        query = select(AIMemoryItem).where(
            AIMemoryItem.subject_type == subject_type,
            AIMemoryItem.subject_id == subject_id,
        )
        if memory_domain is not None:
            query = query.where(AIMemoryItem.memory_domain == memory_domain)
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
            subject_type=query.subject_type,
            subject_id=query.subject_id,
            memory_domain=query.memory_domain,
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
        vector_json = json.dumps(embed_text(content))
        if row is None:
            row = AIMemoryEmbedding(
                memory_id=memory_id,
                embedding_model=EMBEDDING_MODEL_NAME,
                vector_json=vector_json,
            )
            session.add(row)
        else:
            row.embedding_model = EMBEDDING_MODEL_NAME
            row.vector_json = vector_json
        await session.flush()
        return row

    async def retrieve_knowledge_memories(
        self,
        session: AsyncSession,
        *,
        targets: list[tuple[str, str]],
        query_text: str,
        limit: int,
    ) -> list[AIMemoryDefinition]:
        """Retrieve top-k knowledge memories through local embedding similarity."""

        if limit <= 0 or not query_text.strip():
            return []

        query_vector = embed_text(query_text)
        scored: list[tuple[float, AIMemoryDefinition]] = []
        seen_memory_ids: set[str] = set()

        for subject_type, subject_id in targets:
            memories = await self.list_memories(
                session,
                subject_type=subject_type,
                subject_id=subject_id,
                memory_domain="knowledge",
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
                if embedding_row is None:
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
        return [memory for _, memory in scored[:limit]]

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
                memory_domain=memory.memory_domain,
                memory_type=memory.memory_type,
                subject_type=memory.subject_type,
                subject_id=memory.subject_id,
                content=memory.content,
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

        result = await session.execute(
            select(AIMemoryItem).where(AIMemoryItem.memory_id == memory_id)
        )
        memory = result.scalar_one_or_none()
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

    async def consolidate_subject_memories(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_id: str,
    ) -> None:
        """Build or refresh one deterministic summary memory for the subject."""

        memories = await self.list_memories(
            session,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        summary_content = build_summary_memory_content(memories)
        if summary_content is None:
            return

        existing_summary = next(
            (
                memory
                for memory in memories
                if memory.memory_type == self.SUMMARY_MEMORY_TYPE
                and memory.content.startswith(SUMMARY_NOTE_PREFIX)
            ),
            None,
        )
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
                memory_type=self.SUMMARY_MEMORY_TYPE,
                memory_domain="social",
                subject_type=subject_type,
                subject_id=subject_id,
                content=summary_content,
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
            memory_domain=cast("AIMemoryDomain", row.memory_domain),
            memory_type=cast("AIMemoryType", row.memory_type),
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            content=row.content,
            source_turn_id=row.source_turn_id,
            salience=row.salience,
            confidence=row.confidence,
            last_recalled_at=last_recalled_at,
            created_at=created_at,
        )


ai_memory_service = AIMemoryService()
