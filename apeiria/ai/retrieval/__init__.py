"""Internal retrieval candidate layer."""

from __future__ import annotations

from .identity import content_hash_for_text, retrieval_document_id
from .models import (
    DenseVectorRecord,
    EmbeddingBuildResult,
    RetrievalCandidate,
    RetrievalDiagnostics,
    RetrievalDocument,
    RetrievalResult,
)
from .service import RetrievalCandidateService, retrieval_candidate_service

__all__ = [
    "DenseVectorRecord",
    "EmbeddingBuildResult",
    "RetrievalCandidate",
    "RetrievalCandidateService",
    "RetrievalDiagnostics",
    "RetrievalDocument",
    "RetrievalResult",
    "content_hash_for_text",
    "retrieval_candidate_service",
    "retrieval_document_id",
]
