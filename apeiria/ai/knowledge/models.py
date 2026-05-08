"""Models for the default knowledge-base RAG domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

KnowledgeDocumentStatus = Literal["pending", "embedded", "degraded", "failed"]
KnowledgeChunkEmbeddingStatus = Literal["missing", "embedded", "stale", "failed"]


@dataclass(frozen=True)
class KnowledgeUploadedChunk:
    """One deterministic chunk produced from an uploaded document."""

    ordinal: int
    chunk_hash: str
    text: str


@dataclass(frozen=True)
class KnowledgeUploadedDocument:
    """Normalized uploaded document and deterministic chunks."""

    title: str
    source_file_name: str
    content_text: str
    content_hash: str
    chunks: tuple[KnowledgeUploadedChunk, ...]


@dataclass(frozen=True)
class KnowledgeDocumentCreate:
    """Payload persisted as a default knowledge document."""

    title: str
    source_file_name: str
    content_text: str
    content_hash: str
    chunks: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class KnowledgeDocumentDefinition:
    """Persisted default knowledge document metadata."""

    document_id: str
    title: str
    source_file_name: str
    content_text: str
    content_hash: str
    status: KnowledgeDocumentStatus
    chunk_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class KnowledgeChunkDefinition:
    """Persisted chunk metadata and text for retrieval."""

    chunk_id: str
    document_id: str
    ordinal: int
    chunk_hash: str
    text: str
    char_count: int
    embedding_model: str | None
    embedding_status: KnowledgeChunkEmbeddingStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class KnowledgeRebuildDiagnostics:
    """Embedding rebuild counters for knowledge chunks."""

    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    stale_cleanup_count: int = 0


@dataclass(frozen=True)
class KnowledgeUploadResult:
    """Result of one upload and initial embedding pass."""

    document: KnowledgeDocumentDefinition
    chunks: tuple[KnowledgeChunkDefinition, ...]
    diagnostics: KnowledgeRebuildDiagnostics


@dataclass(frozen=True)
class KnowledgeRetrievalDiagnostics:
    """Bounded diagnostics for one knowledge retrieval."""

    candidate_count: int = 0
    selected_count: int = 0
    missing_embedding_count: int = 0
    stale_embedding_count: int = 0
    rerank_status: str = "not_configured"
    degradation_reason: str | None = None


@dataclass(frozen=True)
class KnowledgeRetrievalItem:
    """Prompt-facing selected chunk returned by retrieval."""

    label: str
    document_id: str
    chunk_id: str
    title: str
    source_file_name: str
    rank: int
    score: float
    rerank_score: float | None
    excerpt: str


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    """Selected chunks plus bounded retrieval diagnostics."""

    items: tuple[KnowledgeRetrievalItem, ...]
    diagnostics: KnowledgeRetrievalDiagnostics
