"""Schema models for default knowledge-base routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeChunkDefinition,
        KnowledgeDocumentDefinition,
        KnowledgeRebuildDiagnostics,
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
        KnowledgeRetrievalResult,
        KnowledgeUploadResult,
    )
    from apeiria.app.ai.operations.knowledge import KnowledgeState


class AIKnowledgeStateItem(BaseModel):
    rag_enabled: bool
    document_count: int
    chunk_count: int


class AIKnowledgeStateUpdateRequest(BaseModel):
    rag_enabled: bool


class AIKnowledgeDocumentUploadRequest(BaseModel):
    source_file_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class AIKnowledgeDocumentItem(BaseModel):
    document_id: str
    title: str
    source_file_name: str
    content_hash: str
    status: str
    chunk_count: int
    last_error: str | None = None
    created_at: str
    updated_at: str


class AIKnowledgeChunkItem(BaseModel):
    chunk_id: str
    document_id: str
    ordinal: int
    chunk_hash: str
    text: str
    char_count: int
    embedding_model: str | None = None
    embedding_status: str
    created_at: str
    updated_at: str


class AIKnowledgeRebuildDiagnosticsItem(BaseModel):
    processed_count: int
    skipped_count: int
    failed_count: int
    stale_cleanup_count: int


class AIKnowledgeUploadResultItem(BaseModel):
    document: AIKnowledgeDocumentItem
    chunks: list[AIKnowledgeChunkItem]
    diagnostics: AIKnowledgeRebuildDiagnosticsItem


class AIKnowledgeRetrievalPreviewRequest(BaseModel):
    query_text: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=4, ge=1, le=20)


class AIKnowledgeRetrievalItem(BaseModel):
    label: str
    document_id: str
    chunk_id: str
    title: str
    source_file_name: str
    rank: int
    score: float
    rerank_score: float | None = None
    excerpt: str


class AIKnowledgeRetrievalDiagnosticsItem(BaseModel):
    candidate_count: int
    selected_count: int
    missing_embedding_count: int
    stale_embedding_count: int
    rerank_status: str
    degradation_reason: str | None = None


class AIKnowledgeRetrievalResultItem(BaseModel):
    items: list[AIKnowledgeRetrievalItem]
    diagnostics: AIKnowledgeRetrievalDiagnosticsItem


class AIKnowledgeDeleteResult(BaseModel):
    deleted: bool


def to_knowledge_state_item(state: "KnowledgeState") -> AIKnowledgeStateItem:
    return AIKnowledgeStateItem(
        rag_enabled=state.rag_enabled,
        document_count=state.document_count,
        chunk_count=state.chunk_count,
    )


def to_knowledge_document_item(
    document: "KnowledgeDocumentDefinition",
) -> AIKnowledgeDocumentItem:
    return AIKnowledgeDocumentItem(
        document_id=document.document_id,
        title=document.title,
        source_file_name=document.source_file_name,
        content_hash=document.content_hash,
        status=document.status,
        chunk_count=document.chunk_count,
        last_error=document.last_error,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


def to_knowledge_chunk_item(chunk: "KnowledgeChunkDefinition") -> AIKnowledgeChunkItem:
    return AIKnowledgeChunkItem(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        ordinal=chunk.ordinal,
        chunk_hash=chunk.chunk_hash,
        text=chunk.text,
        char_count=chunk.char_count,
        embedding_model=chunk.embedding_model,
        embedding_status=chunk.embedding_status,
        created_at=chunk.created_at.isoformat(),
        updated_at=chunk.updated_at.isoformat(),
    )


def to_rebuild_diagnostics_item(
    diagnostics: "KnowledgeRebuildDiagnostics",
) -> AIKnowledgeRebuildDiagnosticsItem:
    return AIKnowledgeRebuildDiagnosticsItem(
        processed_count=diagnostics.processed_count,
        skipped_count=diagnostics.skipped_count,
        failed_count=diagnostics.failed_count,
        stale_cleanup_count=diagnostics.stale_cleanup_count,
    )


def to_upload_result_item(
    result: "KnowledgeUploadResult",
) -> AIKnowledgeUploadResultItem:
    return AIKnowledgeUploadResultItem(
        document=to_knowledge_document_item(result.document),
        chunks=[to_knowledge_chunk_item(chunk) for chunk in result.chunks],
        diagnostics=to_rebuild_diagnostics_item(result.diagnostics),
    )


def to_retrieval_item(item: "KnowledgeRetrievalItem") -> AIKnowledgeRetrievalItem:
    return AIKnowledgeRetrievalItem(
        label=item.label,
        document_id=item.document_id,
        chunk_id=item.chunk_id,
        title=item.title,
        source_file_name=item.source_file_name,
        rank=item.rank,
        score=item.score,
        rerank_score=item.rerank_score,
        excerpt=item.excerpt,
    )


def to_retrieval_diagnostics_item(
    diagnostics: "KnowledgeRetrievalDiagnostics",
) -> AIKnowledgeRetrievalDiagnosticsItem:
    return AIKnowledgeRetrievalDiagnosticsItem(
        candidate_count=diagnostics.candidate_count,
        selected_count=diagnostics.selected_count,
        missing_embedding_count=diagnostics.missing_embedding_count,
        stale_embedding_count=diagnostics.stale_embedding_count,
        rerank_status=diagnostics.rerank_status,
        degradation_reason=diagnostics.degradation_reason,
    )


def to_retrieval_result_item(
    result: "KnowledgeRetrievalResult",
) -> AIKnowledgeRetrievalResultItem:
    return AIKnowledgeRetrievalResultItem(
        items=[to_retrieval_item(item) for item in result.items],
        diagnostics=to_retrieval_diagnostics_item(result.diagnostics),
    )
