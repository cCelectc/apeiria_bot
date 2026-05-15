"""Knowledge-memory retrieval coordination through the shared retrieval layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.memory.embedding_store import ai_memory_embedding_store
from apeiria.ai.retrieval import (
    DenseVectorRecord,
    RetrievalCandidateService,
    RetrievalDocument,
    content_hash_for_text,
    retrieval_candidate_service,
    retrieval_document_id,
)

if TYPE_CHECKING:
    from apeiria.ai.memory.contracts import AIMemoryCreateInput
    from apeiria.ai.memory.embedding_store import AIMemoryEmbeddingRecord
    from apeiria.ai.memory.models import AIMemoryAnchorType, AIMemoryDefinition
    from apeiria.ai.memory.repository import AIMemoryRepository


class KnowledgeMemoryCoordinator:
    """Own knowledge-memory indexing and shared candidate retrieval."""

    def __init__(
        self,
        repository: "AIMemoryRepository",
        *,
        retrieval: RetrievalCandidateService | None = None,
    ) -> None:
        self._repository = repository
        self._retrieval = retrieval or retrieval_candidate_service

    async def create_knowledge_memory(
        self,
        create_input: "AIMemoryCreateInput",
    ) -> "AIMemoryDefinition":
        memory = self._repository.create_memory(
            create_input,
            ignore_existing=True,
        )
        if memory is None:
            existing = self._repository.get_memory_by_identity(create_input)
            assert existing is not None
            memory = existing
        return memory

    async def upsert_memory_embedding(
        self,
        *,
        memory_id: str,
        content: str,
    ) -> "AIMemoryEmbeddingRecord | None":
        memory = self._repository.get_memory(memory_id=memory_id)
        document = _memory_to_retrieval_document(
            memory_id=memory_id,
            content=content,
            memory=memory,
        )
        embedding = await self._retrieval.build_embedding_for_document(document)
        if embedding is None:
            return None
        return ai_memory_embedding_store.upsert(
            memory_id=memory_id,
            embedding_model=embedding.embedding_model_label,
            embedding_space_id=embedding.embedding_space_id,
            content_hash=document.content_hash,
            vector=list(embedding.vector),
        )

    def delete_memory_embedding(
        self,
        *,
        memory_id: str,
    ) -> bool:
        return ai_memory_embedding_store.delete(memory_id=memory_id)

    async def retrieve_knowledge_memories(
        self,
        *,
        targets: list[tuple["AIMemoryAnchorType", str]],
        query_text: str,
        limit: int,
    ) -> list["AIMemoryDefinition"]:
        if limit <= 0 or not query_text.strip():
            return []

        seen_memory_ids: set[str] = set()
        memories: list[AIMemoryDefinition] = []
        for anchor_type, anchor_id in targets:
            for memory in self._repository.list_memories(
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                memory_layer="knowledge",
            ):
                if memory.memory_id in seen_memory_ids:
                    continue
                if memory.default_use_mode == "ignore":
                    continue
                seen_memory_ids.add(memory.memory_id)
                memories.append(memory)

        documents = tuple(
            _memory_to_retrieval_document(
                memory_id=memory.memory_id,
                content=memory.content,
                memory=memory,
            )
            for memory in memories
        )
        dense_records = tuple(_memory_to_dense_record(memory) for memory in memories)
        result = await self._retrieval.retrieve_candidates(
            query_text=query_text,
            documents=documents,
            limit=limit,
            allow_rerank=True,
            dense_records=dense_records,
        )
        memory_by_id = {memory.memory_id: memory for memory in memories}
        ranked: list[AIMemoryDefinition] = []
        for candidate in result.candidates:
            memory_id = _memory_id_from_document(candidate.document)
            memory = memory_by_id.get(memory_id)
            if memory is not None:
                ranked.append(memory)
        return ranked


def _memory_to_retrieval_document(
    *,
    memory_id: str,
    content: str,
    memory: "AIMemoryDefinition | None",
) -> RetrievalDocument:
    layer = memory.memory_layer if memory is not None else "knowledge"
    kind = memory.memory_kind if memory is not None else "note"
    title = f"{layer}:{kind}"
    return RetrievalDocument(
        document_id=retrieval_document_id(domain="memory", source_id=memory_id),
        domain="memory",
        title=title,
        text=content,
        content_hash=content_hash_for_text(title, content, layer, kind),
        updated_at=memory.created_at.isoformat() if memory is not None else None,
        metadata={"memory_id": memory_id},
    )


def _memory_to_dense_record(memory: "AIMemoryDefinition") -> DenseVectorRecord:
    document_id = retrieval_document_id(domain="memory", source_id=memory.memory_id)
    embedding = ai_memory_embedding_store.get(memory_id=memory.memory_id)
    if embedding is None:
        return DenseVectorRecord(
            document_id=document_id,
            embedding_space_id=None,
            dimension=0,
            vector=(),
            content_hash=None,
        )
    return DenseVectorRecord(
        document_id=document_id,
        embedding_space_id=embedding.embedding_space_id,
        dimension=embedding.dimension or len(embedding.vector),
        vector=tuple(embedding.vector),
        content_hash=embedding.content_hash,
    )


def _memory_id_from_document(document: RetrievalDocument) -> str:
    memory_id = document.metadata.get("memory_id")
    if isinstance(memory_id, str):
        return memory_id
    prefix = "memory:"
    if document.document_id.startswith(prefix):
        return document.document_id[len(prefix) :]
    return document.document_id
