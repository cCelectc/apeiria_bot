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
from apeiria.ai.retrieval import (
    DenseVectorRecord,
    RetrievalCandidateService,
    RetrievalDocument,
    content_hash_for_text,
    retrieval_candidate_service,
    retrieval_document_id,
)

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeChunkDefinition,
        KnowledgeDocumentDefinition,
    )


class KnowledgeRetrievalService:
    """Small service boundary for the default knowledge base."""

    DEFAULT_CANDIDATE_LIMIT = 12

    def __init__(
        self,
        *,
        repository: KnowledgeRepository | None = None,
        retrieval: RetrievalCandidateService | None = None,
    ) -> None:
        self._repository = repository or KnowledgeRepository()
        self._retrieval = retrieval or retrieval_candidate_service

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
        self._index_chunks(document_id=document.document_id)
        diagnostics = await self.rebuild_embeddings(document_id=document.document_id)
        chunks = tuple(self._repository.list_chunks(document_id=document.document_id))
        refreshed = self._repository.get_document(document_id=document.document_id)
        assert refreshed is not None
        return KnowledgeUploadResult(
            document=refreshed,
            chunks=chunks,
            diagnostics=diagnostics,
        )

    def replace_document_content(
        self,
        *,
        document_id: str,
        source_file_name: str,
        content: str | bytes,
    ) -> KnowledgeUploadResult | None:
        """Replace one knowledge document and refresh retrieval indexes."""

        existing_chunks = tuple(self._repository.list_chunks(document_id=document_id))
        uploaded = chunk_uploaded_document(
            source_file_name=source_file_name,
            content=content,
        )
        document = self._repository._replace_document_content(
            document_id=document_id,
            create_input=KnowledgeDocumentCreate(
                title=uploaded.title,
                source_file_name=uploaded.source_file_name,
                content_text=uploaded.content_text,
                content_hash=uploaded.content_hash,
                chunks=tuple(
                    (chunk.chunk_hash, chunk.text) for chunk in uploaded.chunks
                ),
            ),
        )
        if document is None:
            return None
        self._retrieval.delete_documents(
            tuple(
                retrieval_document_id(domain="knowledge", source_id=chunk.chunk_id)
                for chunk in existing_chunks
            )
        )
        for chunk in existing_chunks:
            chunk_embedding_store.delete(chunk_id=chunk.chunk_id)
        self._index_chunks(document_id=document_id)
        chunks = tuple(self._repository.list_chunks(document_id=document_id))
        return KnowledgeUploadResult(
            document=document,
            chunks=chunks,
            diagnostics=KnowledgeRebuildDiagnostics(),
        )

    async def rebuild_embeddings(
        self,
        *,
        document_id: str | None = None,
    ) -> KnowledgeRebuildDiagnostics:
        chunks = self._repository.list_chunks(document_id=document_id)
        processed = 0
        skipped = 0
        failed = 0
        model_name: str | None = None
        embedded_chunk_ids: list[str] = []
        documents = {
            document.document_id: document
            for document in self._repository.list_documents()
        }
        for chunk in chunks:
            try:
                document = documents.get(chunk.document_id)
                retrieval_document = _chunk_to_retrieval_document(
                    chunk=chunk,
                    document=document,
                )
                embedding = await self._retrieval.build_embedding_for_document(
                    retrieval_document,
                )
                if embedding is None:
                    skipped += 1
                    continue
                model_name = embedding.embedding_model_label
                chunk_embedding_store.upsert(
                    chunk_id=chunk.chunk_id,
                    embedding_model=model_name,
                    embedding_space_id=embedding.embedding_space_id,
                    content_hash=retrieval_document.content_hash,
                    vector=list(embedding.vector),
                )
            except Exception:  # noqa: BLE001
                failed += 1
                continue
            processed += 1
            embedded_chunk_ids.append(chunk.chunk_id)

        if document_id is not None:
            self._repository.mark_chunk_embeddings(
                document_id=document_id,
                chunk_ids=embedded_chunk_ids,
                embedding_model=model_name or "",
                status="embedded",
            )
            self._repository.mark_document_status(
                document_id=document_id,
                status=_document_status_for_rebuild(
                    processed=processed,
                    skipped=skipped,
                    failed=failed,
                ),
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
            skipped_count=skipped,
            failed_count=failed,
        )

    async def retrieve(
        self,
        *,
        query_text: str,
        limit: int,
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

        documents = {
            document.document_id: document
            for document in self._repository.list_documents()
        }
        chunks = _available_chunks(
            chunks=self._repository.list_chunks(),
            documents=documents,
        )
        retrieval_documents = tuple(
            _chunk_to_retrieval_document(
                chunk=chunk,
                document=documents.get(chunk.document_id),
            )
            for chunk in chunks
        )
        dense_records = tuple(_chunk_to_dense_record(chunk) for chunk in chunks)
        dense_records = tuple(record for record in dense_records if record is not None)
        result = await self._retrieval.retrieve_candidates(
            query_text=query_text,
            documents=retrieval_documents,
            limit=limit,
            candidate_limit=max(limit, self.DEFAULT_CANDIDATE_LIMIT),
            allow_rerank=True,
            dense_records=dense_records,
        )
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        items = tuple(
            self._to_retrieval_item(
                label=f"K{index + 1}",
                rank=index + 1,
                score=candidate.rerank_score or candidate.score,
                rerank_score=candidate.rerank_score,
                chunk=chunk,
                document=documents.get(chunk.document_id),
            )
            for index, candidate in enumerate(result.candidates)
            if (chunk := chunks_by_id.get(_source_id_from_document(candidate.document)))
            is not None
        )
        return KnowledgeRetrievalResult(
            items=items,
            diagnostics=KnowledgeRetrievalDiagnostics(
                candidate_count=result.diagnostics.candidate_count,
                selected_count=len(items),
                missing_embedding_count=result.diagnostics.missing_embedding_count,
                stale_embedding_count=result.diagnostics.stale_embedding_count,
                rerank_status=result.diagnostics.rerank_status,
                degradation_reason=result.diagnostics.fallback_reason,
            ),
        )

    def delete_document(self, *, document_id: str) -> bool:
        """Delete one knowledge document and associated retrieval index records."""

        chunk_ids = tuple(
            chunk.chunk_id
            for chunk in self._repository.list_chunks(document_id=document_id)
        )
        deleted = self._repository.delete_document(document_id=document_id)
        if deleted:
            self._retrieval.delete_documents(
                tuple(
                    retrieval_document_id(domain="knowledge", source_id=chunk_id)
                    for chunk_id in chunk_ids
                )
            )
            for chunk_id in chunk_ids:
                chunk_embedding_store.delete(chunk_id=chunk_id)
        return deleted

    def _index_chunks(self, *, document_id: str | None = None) -> None:
        documents = {
            document.document_id: document
            for document in self._repository.list_documents()
        }
        retrieval_documents = tuple(
            _chunk_to_retrieval_document(
                chunk=chunk,
                document=documents.get(chunk.document_id),
            )
            for chunk in self._repository.list_chunks(document_id=document_id)
        )
        self._retrieval.index_documents(retrieval_documents)

    @staticmethod
    def _to_retrieval_item(  # noqa: PLR0913
        *,
        label: str,
        rank: int,
        score: float,
        rerank_score: float | None,
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
            rerank_score=rerank_score,
            excerpt=_excerpt(chunk.text),
        )


def _excerpt(text: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 1].rstrip()}..."


def _chunk_to_retrieval_document(
    *,
    chunk: "KnowledgeChunkDefinition",
    document: "KnowledgeDocumentDefinition | None",
) -> RetrievalDocument:
    title = document.title if document is not None else None
    source_file_name = document.source_file_name if document is not None else None
    return RetrievalDocument(
        document_id=retrieval_document_id(domain="knowledge", source_id=chunk.chunk_id),
        domain="knowledge",
        title=title,
        text=chunk.text,
        content_hash=content_hash_for_text(title, chunk.chunk_hash, chunk.text),
        updated_at=chunk.updated_at.isoformat(),
        metadata={
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source_file_name": source_file_name,
        },
    )


def _chunk_to_dense_record(
    chunk: "KnowledgeChunkDefinition",
) -> DenseVectorRecord | None:
    embedding = chunk_embedding_store.get(chunk_id=chunk.chunk_id)
    if embedding is None:
        return None
    return DenseVectorRecord(
        document_id=retrieval_document_id(domain="knowledge", source_id=chunk.chunk_id),
        embedding_space_id=embedding.embedding_space_id,
        dimension=embedding.dimension or len(embedding.vector),
        vector=tuple(embedding.vector),
        content_hash=embedding.content_hash,
    )


def _available_chunks(
    *,
    chunks: list["KnowledgeChunkDefinition"],
    documents: dict[str, "KnowledgeDocumentDefinition"],
) -> tuple["KnowledgeChunkDefinition", ...]:
    return tuple(
        chunk
        for chunk in chunks
        if _is_knowledge_document_available(documents.get(chunk.document_id))
        and _is_knowledge_chunk_available(chunk)
    )


def _is_knowledge_document_available(
    document: "KnowledgeDocumentDefinition | None",
) -> bool:
    return document is not None and document.status != "failed"


def _is_knowledge_chunk_available(chunk: "KnowledgeChunkDefinition") -> bool:
    return chunk.embedding_status != "failed"


def _source_id_from_document(document: RetrievalDocument) -> str:
    chunk_id = document.metadata.get("chunk_id")
    if isinstance(chunk_id, str):
        return chunk_id
    prefix = "knowledge:"
    if document.document_id.startswith(prefix):
        return document.document_id[len(prefix) :]
    return document.document_id


def _document_status_for_rebuild(
    *,
    processed: int,
    skipped: int,
    failed: int,
) -> str:
    if failed > 0:
        return "degraded"
    if processed > 0 and skipped == 0:
        return "embedded"
    if processed > 0:
        return "degraded"
    return "pending"


knowledge_retrieval_service = KnowledgeRetrievalService()

__all__ = [
    "KnowledgeRetrievalService",
    "knowledge_retrieval_service",
]
