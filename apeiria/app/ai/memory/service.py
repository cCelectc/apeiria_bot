"""Memory CRUD and retrieval service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.memory.models import (
    AIMemoryDefinition,
    AIMemoryQuery,
    AIMemoryType,
)
from apeiria.app.ai.memory.ranking import rank_memory_items
from apeiria.infra.db.models import AIMemoryItem

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIMemoryCreateInput:
    """Create payload for one structured memory item."""

    memory_type: AIMemoryType
    subject_type: str
    subject_id: str
    content: str
    source_turn_id: str | None = None
    salience: float = 0.5
    confidence: float = 0.5


class AIMemoryService:
    """Long-term memory CRUD and retrieval service."""

    async def create_memory(
        self,
        session: AsyncSession,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryItem:
        """Create one structured memory item."""

        memory = AIMemoryItem(
            memory_id=f"mem_{uuid4().hex}",
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

    async def list_memories(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_id: str,
    ) -> list[AIMemoryDefinition]:
        """List all memories for one subject boundary."""

        result = await session.execute(
            select(AIMemoryItem)
            .where(
                AIMemoryItem.subject_type == subject_type,
                AIMemoryItem.subject_id == subject_id,
            )
            .order_by(AIMemoryItem.created_at.asc(), AIMemoryItem.id.asc())
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
        )
        return rank_memory_items(memories, query)

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
        await session.delete(memory)
        return True

    async def consolidate_subject_memories(
        self,
        session: AsyncSession,
        *,
        subject_type: str,
        subject_id: str,
    ) -> None:
        """Stub for later background memory consolidation.

        Phase 4 only introduces the boundary and API surface. Actual extraction
        and compaction policies land in later rounds.
        """

        _ = await self.list_memories(
            session,
            subject_type=subject_type,
            subject_id=subject_id,
        )

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
