"""Default knowledge-base upload, embedding, and retrieval service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.knowledge.chunking import chunk_uploaded_document
from apeiria.ai.knowledge.embedding_store import chunk_embedding_store
from apeiria.ai.knowledge.models import (
    KnowledgeDocumentCreate,
    KnowledgeRebuildDiagnostics,
    KnowledgeRetrievalDiagnostics,
    KnowledgeRetrievalItem,
    KnowledgeRetrievalResult,
    KnowledgeUploadResult,
)
from apeiria.ai.knowledge.repository import KnowledgeRepository
from apeiria.ai.memory.embeddings import (
    EMBEDDING_MODEL_NAME,
    cosine_similarity,
    embed_text,
)
from apeiria.ai.model.routing.capability_selection import (
    ai_model_capability_selection_service,
)
from apeiria.ai.model.runtime.service import model_invoker
from apeiria.ai.model.sources.service import ai_source_service

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeChunkDefinition,
        KnowledgeDocumentDefinition,
    )


class KnowledgeRetrievalService:
    """Small service boundary for the default knowledge base."""

    RERANK_CANDIDATE_MULTIPLIER = 4
    RERANK_MIN_CANDIDATES = 8
    DEFAULT_CANDIDATE_LIMIT = 12

    def __init__(
        self,
        *,
        repository: KnowledgeRepository | None = None,
    ) -> None:
        self._repository = repository or KnowledgeRepository()

    async def upload_document(
        self,
        *,
        source_file_name: str,
        content: str | bytes,
    ) -> KnowledgeUploadResult:
        uploaded = chunk_uploaded_document(
            source_file_name=source_file_name,
            content=content,
        )
        document = self._repository.create_document(
            KnowledgeDocumentCreate(
                title=uploaded.title,
                source_file_name=uploaded.source_file_name,
                content_text=uploaded.content_text,
                content_hash=uploaded.content_hash,
                chunks=tuple(
                    (chunk.chunk_hash, chunk.text) for chunk in uploaded.chunks
                ),
            )
        )
        diagnostics = await self.rebuild_embeddings(document_id=document.document_id)
        chunks = tuple(self._repository.list_chunks(document_id=document.document_id))
        refreshed = self._repository.get_document(document_id=document.document_id)
        assert refreshed is not None
        return KnowledgeUploadResult(
            document=refreshed,
            chunks=chunks,
            diagnostics=diagnostics,
        )

    async def rebuild_embeddings(
        self,
        *,
        document_id: str | None = None,
    ) -> KnowledgeRebuildDiagnostics:
        chunks = self._repository.list_chunks(document_id=document_id)
        processed = 0
        failed = 0
        model_name: str | None = None
        embedded_chunk_ids: list[str] = []
        for chunk in chunks:
            try:
                model_name, vector = await self._build_embedding_vector(chunk.text)
                chunk_embedding_store.upsert(
                    chunk_id=chunk.chunk_id,
                    embedding_model=model_name,
                    vector=vector,
                )
            except Exception:  # noqa: BLE001
                failed += 1
                continue
            processed += 1
            embedded_chunk_ids.append(chunk.chunk_id)

        if document_id is not None and model_name is not None:
            self._repository.mark_chunk_embeddings(
                document_id=document_id,
                chunk_ids=embedded_chunk_ids,
                embedding_model=model_name,
                status="embedded",
            )
            self._repository.mark_document_status(
                document_id=document_id,
                status="embedded" if failed == 0 else "degraded",
            )
        elif model_name is not None:
            by_document: dict[str, list[str]] = {}
            for chunk in chunks:
                if chunk.chunk_id in embedded_chunk_ids:
                    by_document.setdefault(chunk.document_id, []).append(chunk.chunk_id)
            for chunk_document_id, chunk_ids in by_document.items():
                self._repository.mark_chunk_embeddings(
                    document_id=chunk_document_id,
                    chunk_ids=chunk_ids,
                    embedding_model=model_name,
                    status="embedded",
                )

        return KnowledgeRebuildDiagnostics(
            processed_count=processed,
            failed_count=failed,
        )

    async def preview_retrieval(
        self,
        *,
        query_text: str,
        limit: int,
    ) -> KnowledgeRetrievalResult:
        return await self.retrieve(
            query_text=query_text,
            limit=limit,
            mutate_embeddings=False,
        )

    async def retrieve(
        self,
        *,
        query_text: str,
        limit: int,
        mutate_embeddings: bool = False,
        candidate_limit: int | None = None,
    ) -> KnowledgeRetrievalResult:
        if limit <= 0:
            return KnowledgeRetrievalResult(
                items=(),
                diagnostics=KnowledgeRetrievalDiagnostics(
                    degradation_reason="invalid_limit"
                ),
            )
        if not query_text.strip():
            return KnowledgeRetrievalResult(
                items=(),
                diagnostics=KnowledgeRetrievalDiagnostics(
                    degradation_reason="empty_query"
                ),
            )

        embedding_model, query_vector = await self._build_embedding_vector(query_text)
        chunks = self._repository.list_chunks()
        documents = {
            document.document_id: document
            for document in self._repository.list_documents()
        }
        scored: list[tuple[float, KnowledgeChunkDefinition]] = []
        missing_embedding_count = 0
        stale_embedding_count = 0
        for chunk in chunks:
            embedding = chunk_embedding_store.get(chunk_id=chunk.chunk_id)
            if embedding is None:
                missing_embedding_count += 1
                if not mutate_embeddings:
                    continue
                embedding_model, vector = await self._build_embedding_vector(chunk.text)
                embedding = chunk_embedding_store.upsert(
                    chunk_id=chunk.chunk_id,
                    embedding_model=embedding_model,
                    vector=vector,
                )
            if embedding.embedding_model != embedding_model:
                stale_embedding_count += 1
                continue
            scored.append((cosine_similarity(query_vector, embedding.vector), chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        bounded_candidates = scored[
            : candidate_limit or max(limit, self.DEFAULT_CANDIDATE_LIMIT)
        ]
        ranked, rerank_status = await self._maybe_rerank(
            query_text=query_text,
            candidates=bounded_candidates,
            limit=limit,
        )
        selected = ranked[:limit]
        items = tuple(
            self._to_retrieval_item(
                label=f"K{index + 1}",
                rank=index + 1,
                score=score,
                chunk=chunk,
                document=documents.get(chunk.document_id),
            )
            for index, (score, chunk) in enumerate(selected)
        )
        return KnowledgeRetrievalResult(
            items=items,
            diagnostics=KnowledgeRetrievalDiagnostics(
                candidate_count=len(bounded_candidates),
                selected_count=len(items),
                missing_embedding_count=missing_embedding_count,
                stale_embedding_count=stale_embedding_count,
                rerank_status=rerank_status,
            ),
        )

    async def _build_embedding_vector(
        self,
        content: str,
    ) -> tuple[str, list[float]]:
        selected = await ai_model_capability_selection_service.select_default_model(
            capability_type="embedding",
        )
        if selected is None:
            return EMBEDDING_MODEL_NAME, embed_text(content)

        try:
            api_key = ai_source_service.get_source_api_key(selected.source)
            if not api_key:
                return EMBEDDING_MODEL_NAME, embed_text(content)
            response = await model_invoker.embed_texts_for_source(
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

    async def _maybe_rerank(
        self,
        *,
        query_text: str,
        candidates: list[tuple[float, "KnowledgeChunkDefinition"]],
        limit: int,
    ) -> tuple[list[tuple[float, "KnowledgeChunkDefinition"]], str]:
        if not candidates:
            return [], "not_applicable"
        selected = await ai_model_capability_selection_service.select_default_model(
            capability_type="rerank",
        )
        if selected is None:
            return candidates, "not_configured"
        api_key = ai_source_service.get_source_api_key(selected.source)
        if not api_key:
            return candidates, "skipped"

        candidate_limit = min(
            len(candidates),
            max(limit * self.RERANK_CANDIDATE_MULTIPLIER, self.RERANK_MIN_CANDIDATES),
        )
        limited = candidates[:candidate_limit]
        try:
            response = await model_invoker.rerank_documents_for_source(
                source=selected.source,
                api_key=api_key,
                model_name=selected.model.model_identifier,
                query=query_text,
                documents=tuple(chunk.text for _, chunk in limited),
                top_n=min(limit, len(limited)),
            )
        except Exception:  # noqa: BLE001
            return candidates, "failed"

        reranked: list[tuple[float, KnowledgeChunkDefinition]] = []
        seen_indexes: set[int] = set()
        for item in response.results:
            if item.index < 0 or item.index >= len(limited):
                continue
            if item.index in seen_indexes:
                continue
            seen_indexes.add(item.index)
            _, chunk = limited[item.index]
            reranked.append((float(item.relevance_score), chunk))

        if not reranked:
            return candidates, "failed"
        tail = [
            candidate
            for index, candidate in enumerate(limited)
            if index not in seen_indexes
        ]
        return (reranked + tail), "applied"

    @staticmethod
    def _to_retrieval_item(
        *,
        label: str,
        rank: int,
        score: float,
        chunk: "KnowledgeChunkDefinition",
        document: "KnowledgeDocumentDefinition | None",
    ) -> KnowledgeRetrievalItem:
        title = document.title if document is not None else chunk.document_id
        source_file_name = (
            document.source_file_name if document is not None else chunk.document_id
        )
        return KnowledgeRetrievalItem(
            label=label,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            title=title,
            source_file_name=source_file_name,
            rank=rank,
            score=score,
            rerank_score=None,
            excerpt=_excerpt(chunk.text),
        )


def _excerpt(text: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


knowledge_retrieval_service = KnowledgeRetrievalService()

__all__ = [
    "KnowledgeRetrievalService",
    "knowledge_retrieval_service",
]
