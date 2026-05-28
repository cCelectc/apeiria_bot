"""Shared rerank handling for retrieval candidates."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.model.routing.capability_selection import (
        AIModelCapabilitySelectionService,
    )
    from apeiria.ai.model.runtime.adapter import AIModelRerankResultItem
    from apeiria.ai.model.runtime.service import ModelInvoker
    from apeiria.ai.model.sources.service import AISourceService
    from apeiria.ai.retrieval.models import (
        RerankStatus,
        RetrievalCandidate,
    )

_RERANK_CANDIDATE_MULTIPLIER = 4
_RERANK_MIN_CANDIDATES = 8
_RERANK_MAX_CANDIDATES = 50


async def maybe_rerank_candidates(  # noqa: PLR0911, PLR0913
    *,
    query_text: str,
    candidates: tuple[RetrievalCandidate, ...],
    limit: int,
    allow_rerank: bool,
    capability_selection_service: "AIModelCapabilitySelectionService",
    model_invoker: "ModelInvoker",
    source_service: "AISourceService",
) -> tuple[tuple[RetrievalCandidate, ...], RerankStatus]:
    """Rerank candidates when a rerank model is configured and usable."""

    if not candidates:
        return candidates, "not_applicable"
    if not allow_rerank or len(candidates) <= 1:
        return candidates[:limit], "skipped"
    selected = await capability_selection_service.select_default_model(
        capability_type="rerank",
    )
    if selected is None:
        return candidates[:limit], "not_configured"
    api_key = source_service.get_source_api_key(selected.source)
    if not api_key:
        return candidates[:limit], "skipped"

    candidate_limit = min(
        len(candidates),
        max(limit * _RERANK_CANDIDATE_MULTIPLIER, _RERANK_MIN_CANDIDATES),
        _RERANK_MAX_CANDIDATES,
    )
    limited = candidates[:candidate_limit]
    try:
        response = await model_invoker.rerank_documents_for_source(
            source=selected.source,
            api_key=api_key,
            model_name=selected.model.model_identifier,
            query=query_text,
            documents=tuple(candidate.document.search_text for candidate in limited),
            top_n=min(limit, len(limited)),
        )
    except Exception:  # noqa: BLE001
        return candidates[:limit], "failed"

    reranked, seen_indexes, has_invalid = _map_rerank_results(
        response.results,
        limited,
        limit,
    )
    if has_invalid:
        return candidates[:limit], "failed"
    if not reranked:
        return candidates[:limit], "failed"
    tail = [
        candidate
        for index, candidate in enumerate(limited)
        if index not in seen_indexes
    ]
    return tuple((reranked + tail)[:limit]), "applied"


def _map_rerank_results(
    results: "Sequence[AIModelRerankResultItem]",
    candidates: tuple["RetrievalCandidate", ...],
    limit: int,
) -> tuple[list["RetrievalCandidate"], set[int], bool]:
    reranked: list[RetrievalCandidate] = []
    seen_indexes: set[int] = set()
    has_invalid = False
    for rank, item in enumerate(results, start=1):
        if item.index < 0 or item.index >= len(candidates):
            has_invalid = True
            continue
        if item.index in seen_indexes:
            has_invalid = True
            continue
        seen_indexes.add(item.index)
        reranked.append(
            candidates[item.index].with_rerank(
                score=float(item.relevance_score),
                rank=rank,
            )
        )
        if len(reranked) >= limit:
            break
    return reranked, seen_indexes, has_invalid
