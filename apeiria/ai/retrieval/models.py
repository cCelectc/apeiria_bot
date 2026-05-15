"""Internal retrieval candidate contracts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

RetrievalDomain = Literal["memory", "knowledge"]
RetrievalChannel = Literal["dense", "sparse"]
RetrievalPath = Literal["dense", "sparse", "none"]
RerankStatus = Literal[
    "not_applicable",
    "not_configured",
    "skipped",
    "failed",
    "applied",
]


@dataclass(frozen=True)
class RetrievalDocument:
    """Runtime projection of one domain object that may be searched."""

    document_id: str
    domain: RetrievalDomain
    text: str
    content_hash: str
    title: str | None = None
    updated_at: str | None = None
    filter_attrs: dict[str, str | int | bool | None] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def search_text(self) -> str:
        """Return text visible to retrieval and rerank models."""

        if self.title and self.title.strip():
            return f"{self.title.strip()}\n\n{self.text}"
        return self.text


@dataclass(frozen=True)
class RetrievalCandidate:
    """One query-time candidate returned by a retrieval path."""

    document: RetrievalDocument
    channel: RetrievalChannel
    score: float
    rank: int
    matched_fields: tuple[str, ...] = ()
    diagnostics: dict[str, object] = field(default_factory=dict)
    rerank_score: float | None = None
    rerank_rank: int | None = None

    def with_rerank(self, *, score: float, rank: int) -> "RetrievalCandidate":
        """Return a copy annotated with rerank ordering metadata."""

        return replace(self, rerank_score=score, rerank_rank=rank)


@dataclass(frozen=True)
class DenseVectorRecord:
    """Stored dense vector metadata for one retrieval document."""

    document_id: str
    embedding_space_id: str | None
    dimension: int
    vector: tuple[float, ...]
    content_hash: str | None


@dataclass(frozen=True)
class EmbeddingBuildResult:
    """One successfully built embedding in a comparable embedding space."""

    embedding_space_id: str
    embedding_model_label: str
    vector: tuple[float, ...]
    dimension: int


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Compact diagnostics for one retrieval operation."""

    path: RetrievalPath = "none"
    fallback_reason: str | None = None
    candidate_count: int = 0
    selected_count: int = 0
    missing_embedding_count: int = 0
    stale_embedding_count: int = 0
    rerank_status: RerankStatus = "not_applicable"


@dataclass(frozen=True)
class RetrievalResult:
    """Candidates plus bounded retrieval diagnostics."""

    candidates: tuple[RetrievalCandidate, ...]
    diagnostics: RetrievalDiagnostics
