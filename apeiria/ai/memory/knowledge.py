"""Knowledge-memory embedding and rerank coordination."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.memory.embedding_store import ai_memory_embedding_store
from apeiria.ai.memory.embeddings import (
    EMBEDDING_MODEL_NAME,
    cosine_similarity,
    embed_text,
)
from apeiria.ai.model.service import ai_model_facade
from apeiria.ai.model.source import ai_source_service

if TYPE_CHECKING:
    from apeiria.ai.memory.contracts import AIMemoryCreateInput
    from apeiria.ai.memory.embedding_store import AIMemoryEmbeddingRecord
    from apeiria.ai.memory.models import AIMemoryAnchorType, AIMemoryDefinition
    from apeiria.ai.memory.repository import AIMemoryRepository


class KnowledgeMemoryCoordinator:
    """Own embedding lookup and model-assisted ranking for knowledge memories."""

    RERANK_CANDIDATE_MULTIPLIER = 4
    RERANK_MIN_CANDIDATES = 8

    def __init__(self, repository: AIMemoryRepository) -> None:
        self._repository = repository

    async def create_knowledge_memory(
        self,
        create_input: AIMemoryCreateInput,
    ) -> AIMemoryDefinition:
        memory = self._repository.create_memory(
            create_input,
            ignore_existing=True,
        )
        if memory is None:
            existing = self._repository.get_memory_by_identity(create_input)
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
        embedding_model, vector = await self._build_knowledge_embedding_vector(
            content=content,
        )
        return ai_memory_embedding_store.upsert(
            memory_id=memory_id,
            embedding_model=embedding_model,
            vector=vector,
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
        targets: list[tuple[AIMemoryAnchorType, str]],
        query_text: str,
        limit: int,
    ) -> list[AIMemoryDefinition]:
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
            memories = self._repository.list_memories(
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
                limit * self.RERANK_CANDIDATE_MULTIPLIER,
                self.RERANK_MIN_CANDIDATES,
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
