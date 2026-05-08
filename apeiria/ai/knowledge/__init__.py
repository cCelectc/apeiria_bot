"""Default knowledge-base RAG domain."""

from __future__ import annotations

from apeiria.ai.knowledge.chunking import (
    KnowledgeUploadValidationError,
    chunk_uploaded_document,
)
from apeiria.ai.knowledge.embedding_store import (
    ChunkEmbeddingRecord,
    ChunkEmbeddingStore,
    chunk_embedding_store,
)
from apeiria.ai.knowledge.models import (
    KnowledgeChunkDefinition,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDefinition,
    KnowledgeUploadedChunk,
    KnowledgeUploadedDocument,
)
from apeiria.ai.knowledge.repository import KnowledgeRepository
from apeiria.ai.knowledge.service import (
    KnowledgeRetrievalService,
    knowledge_retrieval_service,
)

__all__ = [
    "ChunkEmbeddingRecord",
    "ChunkEmbeddingStore",
    "KnowledgeChunkDefinition",
    "KnowledgeDocumentCreate",
    "KnowledgeDocumentDefinition",
    "KnowledgeRepository",
    "KnowledgeRetrievalService",
    "KnowledgeUploadValidationError",
    "KnowledgeUploadedChunk",
    "KnowledgeUploadedDocument",
    "chunk_embedding_store",
    "chunk_uploaded_document",
    "knowledge_retrieval_service",
]
