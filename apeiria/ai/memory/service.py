"""Memory CRUD and retrieval service."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from apeiria.ai.memory.actions import build_memory_write_plans
from apeiria.ai.memory.embedding_store import (
    AIMemoryEmbeddingRecord,
    ai_memory_embedding_store,
)
from apeiria.ai.memory.embeddings import (
    EMBEDDING_MODEL_NAME,
    cosine_similarity,
    embed_text,
)
from apeiria.ai.memory.models import (
    AIMemoryAnchorType,
    AIMemoryDefinition,
    AIMemoryExtractionCandidate,
    AIMemoryKind,
    AIMemoryLayer,
    AIMemoryQuery,
)
from apeiria.ai.memory.ranking import rank_memory_items
from apeiria.ai.memory.summary import build_summary_memory_content
from apeiria.ai.model.service import ai_model_facade
from apeiria.ai.model.source import ai_source_service
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection


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
    source_message_id: str | None = None
    salience: float = 0.5
    confidence: float = 0.5


@dataclass(frozen=True)
class AIMemoryUpdateInput:
    """Update payload for one existing memory item."""

    content: str
    salience: float
    confidence: float
    source_message_id: str | None


@dataclass
class _MemoryRow:
    id: int
    memory_id: str
    anchor_type: str
    anchor_id: str
    memory_layer: str
    memory_kind: str
    content: str
    is_editable: bool
    is_ignored: bool
    source_message_id: str | None
    salience: float
    confidence: float
    last_recalled_at: datetime | None
    created_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_datetime_from_text(value: object | None) -> datetime | None:
    return None if value is None else _datetime_from_text(value)


class AIMemoryService:
    """Long-term memory CRUD and retrieval service."""

    SUMMARY_MEMORY_LAYER: AIMemoryLayer = "summary"
    SUMMARY_MEMORY_KIND: AIMemoryKind = "note"
    KNOWLEDGE_RERANK_CANDIDATE_MULTIPLIER = 4
    KNOWLEDGE_RERANK_MIN_CANDIDATES = 8

    async def create_memory(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition:
        """Create one structured memory item."""
        with database_runtime.transaction_sync() as connection:
            row = self._insert_memory_row(
                connection,
                create_input,
                ignore_existing=False,
            )
        assert row is not None
        return self._to_definition(row)

    async def create_memory_if_absent(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        """Create one memory item only when an identical item does not exist."""
        with database_runtime.transaction_sync() as connection:
            row = self._insert_memory_row(
                connection,
                create_input,
                ignore_existing=True,
            )
        if row is None:
            return None
        return self._to_definition(row)

    @staticmethod
    def _insert_memory_row(
        connection: "Connection",
        create_input: AIMemoryCreateInput,
        *,
        ignore_existing: bool,
    ) -> _MemoryRow | None:
        now = _utcnow()
        memory_id = f"mem_{uuid4().hex}"
        conflict_clause = (
            """
            ON CONFLICT(anchor_type, anchor_id, memory_layer, memory_kind, content)
            DO NOTHING
            """
            if ignore_existing
            else ""
        )
        cursor = connection.execute(
            f"""
            INSERT INTO ai_memory_item (
                memory_id,
                anchor_type,
                anchor_id,
                memory_layer,
                memory_kind,
                content,
                is_editable,
                is_ignored,
                source_message_id,
                salience,
                confidence,
                last_recalled_at,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            {conflict_clause}
            """,
            (
                memory_id,
                create_input.anchor_type,
                create_input.anchor_id,
                create_input.memory_layer,
                create_input.memory_kind,
                create_input.content,
                1 if create_input.is_editable else 0,
                1 if create_input.is_ignored else 0,
                create_input.source_message_id,
                create_input.salience,
                create_input.confidence,
                None,
                _datetime_to_text(now),
            ),
        )
        if cursor.rowcount == 0:
            return None
        return _MemoryRow(
            id=int(cursor.lastrowid or 0),
            memory_id=memory_id,
            anchor_type=create_input.anchor_type,
            anchor_id=create_input.anchor_id,
            memory_layer=create_input.memory_layer,
            memory_kind=create_input.memory_kind,
            content=create_input.content,
            is_editable=create_input.is_editable,
            is_ignored=create_input.is_ignored,
            source_message_id=create_input.source_message_id,
            salience=create_input.salience,
            confidence=create_input.confidence,
            last_recalled_at=None,
            created_at=now,
        )

    async def get_memory_by_identity(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition | None:
        """Load one exact memory row for the given identity tuple."""
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_MEMORY_FIELDS
                + """
                WHERE
                    anchor_type = ?
                    AND anchor_id = ?
                    AND memory_layer = ?
                    AND memory_kind = ?
                    AND content = ?
                """,
                (
                    create_input.anchor_type,
                    create_input.anchor_id,
                    create_input.memory_layer,
                    create_input.memory_kind,
                    create_input.content,
                ),
            ).fetchone()
        if row is None:
            return None
        return self._to_definition(_row_to_memory(row))

    async def get_memory(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        """Load one memory row by stable id."""
        row = self._get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        return self._to_definition(row)

    async def update_memory_content(
        self,
        *,
        memory_id: str,
        update_input: AIMemoryUpdateInput,
    ) -> AIMemoryDefinition | None:
        """Update one existing memory item in place."""
        row = self._get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        row.content = update_input.content
        row.salience = update_input.salience
        row.confidence = update_input.confidence
        row.source_message_id = update_input.source_message_id
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_memory_item
                SET
                    content = ?,
                    salience = ?,
                    confidence = ?,
                    source_message_id = ?
                WHERE memory_id = ?
                """,
                (
                    row.content,
                    row.salience,
                    row.confidence,
                    row.source_message_id,
                    memory_id,
                ),
            )
        return self._to_definition(row)

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
        conditions = ["anchor_type = ?", "anchor_id = ?"]
        params: list[object] = [anchor_type, anchor_id]
        if memory_layer is not None:
            conditions.append("memory_layer = ?")
            params.append(memory_layer)
        if memory_kind is not None:
            conditions.append("memory_kind = ?")
            params.append(memory_kind)
        if not include_ignored:
            conditions.append("is_ignored = 0")

        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_MEMORY_FIELDS
                + f"""
                WHERE {" AND ".join(conditions)}
                ORDER BY created_at ASC, id ASC
                """,
                tuple(params),
            ).fetchall()
        return [self._to_definition(_row_to_memory(row)) for row in rows]

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

        memory = await self.create_memory_if_absent(create_input)
        if memory is None:
            existing = await self.get_memory_by_identity(create_input)
            assert existing is not None
            memory = existing
        await self.upsert_memory_embedding(
            memory_id=memory.memory_id,
            content=memory.content,
        )
        return memory

    async def upsert_memory_embedding(
        self,
        *,
        memory_id: str,
        content: str,
    ) -> AIMemoryEmbeddingRecord:
        """Create or update one file-backed memory embedding."""

        embedding_model, vector = await self._build_knowledge_embedding_vector(
            content=content,
        )
        return ai_memory_embedding_store.upsert(
            memory_id=memory_id,
            embedding_model=embedding_model,
            vector=vector,
        )

    async def retrieve_knowledge_memories(
        self,
        *,
        targets: list[tuple[AIMemoryAnchorType, str]],
        query_text: str,
        limit: int,
    ) -> list[AIMemoryDefinition]:
        """Retrieve top-k knowledge memories through local embedding similarity."""

        if limit <= 0 or not query_text.strip():
            return []

        (
            query_embedding_model,
            query_vector,
        ) = await self._build_knowledge_embedding_vector(
            content=query_text,
        )
        scored: list[tuple[float, AIMemoryDefinition]] = []
        seen_memory_ids: set[str] = set()

        for anchor_type, anchor_id in targets:
            memories = await self.list_memories(
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                memory_layer="knowledge",
            )
            for memory in memories:
                if memory.memory_id in seen_memory_ids:
                    continue
                seen_memory_ids.add(memory.memory_id)
                embedding_row = ai_memory_embedding_store.get(
                    memory_id=memory.memory_id
                )
                if (
                    embedding_row is None
                    or embedding_row.embedding_model != query_embedding_model
                ):
                    embedding_row = await self.upsert_memory_embedding(
                        memory_id=memory.memory_id,
                        content=memory.content,
                    )
                scored.append(
                    (cosine_similarity(query_vector, embedding_row.vector), memory)
                )

        scored.sort(key=lambda item: item[0], reverse=True)
        dense_ranked = [memory for _, memory in scored]
        return await self._rerank_knowledge_memories(
            query_text=query_text,
            memories=dense_ranked,
            limit=limit,
        )

    async def _build_knowledge_embedding_vector(
        self,
        *,
        content: str,
    ) -> tuple[str, list[float]]:
        selected = await ai_model_facade.select_capability_model(
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
        *,
        query_text: str,
        memories: list[AIMemoryDefinition],
        limit: int,
    ) -> list[AIMemoryDefinition]:
        if limit <= 0 or not memories:
            return []

        selected = await ai_model_facade.select_capability_model(
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
        query: AIMemoryQuery,
    ) -> list[AIMemoryDefinition]:
        """Retrieve memories for live AI use and stamp recall time."""

        recalled = await self.retrieve_memories(query)
        if not recalled:
            return []

        recalled_at = _utcnow()
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
        memory = self._get_memory_row(memory_id=memory_id)
        if memory is None:
            return False
        ai_memory_embedding_store.delete(memory_id=memory_id)
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                "DELETE FROM ai_memory_item WHERE memory_id = ?",
                (memory_id,),
            )
        return int(cursor.rowcount or 0) > 0

    async def toggle_memory_ignored(
        self,
        *,
        memory_id: str,
    ) -> AIMemoryDefinition | None:
        """Toggle the is_ignored flag on one memory item."""
        row = self._get_memory_row(memory_id=memory_id)
        if row is None:
            return None
        row.is_ignored = not row.is_ignored
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE ai_memory_item
                SET is_ignored = ?
                WHERE memory_id = ?
                """,
                (1 if row.is_ignored else 0, memory_id),
            )
        return self._to_definition(row)

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
        if not memory_ids:
            return 0
        placeholders = ",".join("?" for _ in memory_ids)
        with database_runtime.connect_sync() as connection:
            cursor = connection.execute(
                f"""
                UPDATE ai_memory_item
                SET is_ignored = ?
                WHERE memory_id IN ({placeholders})
                """,
                (1 if ignored else 0, *memory_ids),
            )
        return int(cursor.rowcount or 0)

    async def consolidate_anchor_summary(
        self,
        *,
        anchor_type: AIMemoryAnchorType,
        anchor_id: str,
    ) -> None:
        """Build or refresh one deterministic summary memory for the anchor."""

        memories = await self.list_memories(
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
        )

        if summary_content is None:
            if existing_summary is not None:
                await self.delete_memory(memory_id=existing_summary.memory_id)
            return

        if existing_summary is not None:
            if existing_summary.content == summary_content:
                return
            await self.update_memory_content(
                memory_id=existing_summary.memory_id,
                update_input=AIMemoryUpdateInput(
                    content=summary_content,
                    salience=0.8,
                    confidence=0.85,
                    source_message_id=existing_summary.source_message_id,
                ),
            )
            return

        await self.create_memory(
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
        *,
        memory_ids: list[str],
        recalled_at: datetime,
    ) -> None:
        if not memory_ids:
            return

        placeholders = ",".join("?" for _ in memory_ids)
        with database_runtime.connect_sync() as connection:
            connection.execute(
                f"""
                UPDATE ai_memory_item
                SET last_recalled_at = ?
                WHERE memory_id IN ({placeholders})
                """,
                (_datetime_to_text(recalled_at), *memory_ids),
            )

    @staticmethod
    def _get_memory_row(*, memory_id: str) -> _MemoryRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_MEMORY_FIELDS + " WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        return None if row is None else _row_to_memory(row)

    @staticmethod
    def _to_definition(row: _MemoryRow) -> AIMemoryDefinition:
        return AIMemoryDefinition(
            memory_id=row.memory_id,
            anchor_type=cast("AIMemoryAnchorType", row.anchor_type),
            anchor_id=row.anchor_id,
            memory_layer=cast("AIMemoryLayer", row.memory_layer),
            memory_kind=cast("AIMemoryKind", row.memory_kind),
            content=row.content,
            is_editable=row.is_editable,
            is_ignored=row.is_ignored,
            source_message_id=row.source_message_id,
            salience=row.salience,
            confidence=row.confidence,
            last_recalled_at=row.last_recalled_at,
            created_at=row.created_at,
        )


_SELECT_MEMORY_FIELDS = """
SELECT
    id,
    memory_id,
    anchor_type,
    anchor_id,
    memory_layer,
    memory_kind,
    content,
    is_editable,
    is_ignored,
    source_message_id,
    salience,
    confidence,
    last_recalled_at,
    created_at
FROM ai_memory_item
"""


def _row_to_memory(row: tuple[object, ...]) -> _MemoryRow:
    return _MemoryRow(
        id=int(str(row[0])),
        memory_id=str(row[1]),
        anchor_type=str(row[2]),
        anchor_id=str(row[3]),
        memory_layer=str(row[4]),
        memory_kind=str(row[5]),
        content=str(row[6]),
        is_editable=bool(row[7]),
        is_ignored=bool(row[8]),
        source_message_id=str(row[9]) if row[9] is not None else None,
        salience=float(str(row[10])),
        confidence=float(str(row[11])),
        last_recalled_at=_optional_datetime_from_text(row[12]),
        created_at=_datetime_from_text(row[13]),
    )


ai_memory_service = AIMemoryService()
