"""Dense retrieval scoring helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apeiria.ai.retrieval.models import (
    DenseVectorRecord,
    RetrievalCandidate,
    RetrievalDocument,
)


@dataclass(frozen=True)
class DenseCandidateResult:
    """Dense candidates plus embedding freshness counters."""

    candidates: tuple[RetrievalCandidate, ...]
    missing_embedding_count: int = 0
    stale_embedding_count: int = 0


def score_dense_candidates(
    *,
    query_vector: tuple[float, ...],
    documents: tuple[RetrievalDocument, ...],
    records: tuple[DenseVectorRecord, ...],
    embedding_space_id: str,
    limit: int,
) -> DenseCandidateResult:
    """Score candidate documents whose vectors are comparable to the query."""

    if limit <= 0:
        return DenseCandidateResult(candidates=())
    records_by_document = {record.document_id: record for record in records}
    scored: list[tuple[float, RetrievalDocument]] = []
    missing_count = 0
    stale_count = 0
    expected_dimension = len(query_vector)
    for document in documents:
        record = records_by_document.get(document.document_id)
        if record is None:
            missing_count += 1
            continue
        if (
            record.embedding_space_id != embedding_space_id
            or record.content_hash != document.content_hash
            or record.dimension != expected_dimension
        ):
            stale_count += 1
            continue
        scored.append((_cosine_similarity(query_vector, record.vector), document))

    scored.sort(key=lambda item: item[0], reverse=True)
    candidates = tuple(
        RetrievalCandidate(
            document=document,
            channel="dense",
            score=score,
            rank=index + 1,
            matched_fields=("text",),
        )
        for index, (score, document) in enumerate(scored[:limit])
    )
    return DenseCandidateResult(
        candidates=candidates,
        missing_embedding_count=missing_count,
        stale_embedding_count=stale_count,
    )


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
