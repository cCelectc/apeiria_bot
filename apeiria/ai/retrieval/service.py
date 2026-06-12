"""Thin orchestration for internal retrieval candidate generation."""

from __future__ import annotations

from apeiria.ai.model.routing.capability_selection import (
    AIModelCapabilitySelectionService,
)
from apeiria.ai.model.runtime.service import ModelInvoker
from apeiria.ai.model.sources.service import AISourceService
from apeiria.ai.retrieval.dense import score_dense_candidates
from apeiria.ai.retrieval.identity import (
    embedding_space_id_for_selected,
    embedding_space_label,
)
from apeiria.ai.retrieval.models import (
    DenseVectorRecord,
    EmbeddingBuildResult,
    RetrievalDiagnostics,
    RetrievalDocument,
    RetrievalResult,
)
from apeiria.ai.retrieval.rerank import maybe_rerank_candidates
from apeiria.ai.retrieval.sparse import RetrievalSparseIndex, retrieval_sparse_index

_DEFAULT_CANDIDATE_LIMIT = 20
_MAX_CANDIDATE_LIMIT = 50


class RetrievalCandidateService:
    """Select dense or sparse candidate generation, then optional rerank."""

    def __init__(
        self,
        *,
        sparse_index: RetrievalSparseIndex | None = None,
        capability_selection_service: AIModelCapabilitySelectionService | None = None,
        model_invoker: ModelInvoker | None = None,
        source_service: AISourceService | None = None,
    ) -> None:
        self._source_service = source_service or AISourceService()
        self._capability_selection_service = (
            capability_selection_service
            or AIModelCapabilitySelectionService(source_service=self._source_service)
        )
        self._model_invoker = model_invoker or ModelInvoker(
            source_service=self._source_service,
        )
        self._sparse_index = sparse_index or retrieval_sparse_index

    async def retrieve_candidates(  # noqa: PLR0913
        self,
        *,
        query_text: str,
        documents: tuple[RetrievalDocument, ...],
        limit: int,
        candidate_limit: int | None = None,
        allow_rerank: bool = True,
        dense_records: tuple[DenseVectorRecord, ...] = (),
    ) -> RetrievalResult:
        """Return ranked retrieval candidates for already-allowed documents."""

        if limit <= 0:
            return RetrievalResult(
                candidates=(),
                diagnostics=RetrievalDiagnostics(fallback_reason="invalid_limit"),
            )
        if not query_text.strip():
            return RetrievalResult(
                candidates=(),
                diagnostics=RetrievalDiagnostics(fallback_reason="empty_query"),
            )
        if not documents:
            return RetrievalResult(
                candidates=(),
                diagnostics=RetrievalDiagnostics(fallback_reason="no_documents"),
            )

        bounded_candidate_limit = _candidate_limit(limit, candidate_limit)
        embedding = await self._build_embedding(content=query_text)
        missing_count = 0
        stale_count = 0
        fallback_reason = embedding.failure_reason
        path = "sparse"
        candidates = ()
        if embedding.result is not None:
            dense_result = score_dense_candidates(
                query_vector=embedding.result.vector,
                documents=documents,
                records=dense_records,
                embedding_space_id=embedding.result.embedding_space_id,
                limit=bounded_candidate_limit,
            )
            missing_count = dense_result.missing_embedding_count
            stale_count = dense_result.stale_embedding_count
            if dense_result.candidates:
                candidates = dense_result.candidates
                path = "dense"
                fallback_reason = None
            else:
                fallback_reason = "no_comparable_dense_vectors"

        if not candidates:
            sparse_result = await self._sparse_index.search(
                query_text=query_text,
                documents=documents,
                limit=bounded_candidate_limit,
            )
            candidates = sparse_result.candidates
            if sparse_result.used_fallback:
                fallback_reason = "sparse_backend_unavailable"

        reranked, rerank_status = await maybe_rerank_candidates(
            query_text=query_text,
            candidates=candidates,
            limit=limit,
            allow_rerank=allow_rerank,
            capability_selection_service=self._capability_selection_service,
            model_invoker=self._model_invoker,
            source_service=self._source_service,
        )
        selected = reranked[:limit]
        return RetrievalResult(
            candidates=selected,
            diagnostics=RetrievalDiagnostics(
                path=path,  # type: ignore[arg-type]
                fallback_reason=fallback_reason,
                candidate_count=len(candidates),
                selected_count=len(selected),
                missing_embedding_count=missing_count,
                stale_embedding_count=stale_count,
                rerank_status=rerank_status,
            ),
        )

    async def build_embedding_for_document(
        self,
        document: RetrievalDocument,
    ) -> EmbeddingBuildResult | None:
        """Build a dense embedding for one retrieval document when configured."""

        embedding = await self._build_embedding(content=document.search_text)
        return embedding.result

    async def index_documents(self, documents: tuple[RetrievalDocument, ...]) -> None:
        """Update the sparse retrieval index for already-projected documents."""

        await self._sparse_index.upsert_many(documents)

    async def delete_documents(self, document_ids: tuple[str, ...]) -> None:
        """Remove documents from the sparse retrieval index."""

        await self._sparse_index.delete_many(document_ids)

    async def _build_embedding(self, *, content: str) -> "_EmbeddingAttempt":
        selected = await self._capability_selection_service.select_default_model(
            capability_type="embedding",
        )
        if selected is None:
            return _EmbeddingAttempt(
                result=None,
                failure_reason="no_embedding_model",
            )
        api_key = self._source_service.get_source_api_key(selected.source)
        if not api_key:
            return _EmbeddingAttempt(
                result=None,
                failure_reason="missing_embedding_credentials",
            )
        try:
            response = await self._model_invoker.embed_texts_for_source(
                source=selected.source,
                api_key=api_key,
                model_name=selected.model.model_identifier,
                texts=(content,),
            )
        except Exception:  # noqa: BLE001
            return _EmbeddingAttempt(
                result=None,
                failure_reason="embedding_failed",
            )
        if not response.vectors:
            return _EmbeddingAttempt(
                result=None,
                failure_reason="embedding_empty",
            )
        vector = tuple(float(value) for value in response.vectors[0])
        if not vector:
            return _EmbeddingAttempt(
                result=None,
                failure_reason="embedding_empty",
            )
        dimension = len(vector)
        return _EmbeddingAttempt(
            result=EmbeddingBuildResult(
                embedding_space_id=embedding_space_id_for_selected(
                    selected,
                    dimension=dimension,
                ),
                embedding_model_label=embedding_space_label(
                    selected,
                    dimension=dimension,
                ),
                vector=vector,
                dimension=dimension,
            ),
            failure_reason=None,
        )


class _EmbeddingAttempt:
    def __init__(
        self,
        *,
        result: EmbeddingBuildResult | None,
        failure_reason: str | None,
    ) -> None:
        self.result = result
        self.failure_reason = failure_reason


def _candidate_limit(limit: int, candidate_limit: int | None) -> int:
    requested = candidate_limit or max(limit * 4, _DEFAULT_CANDIDATE_LIMIT)
    return min(max(requested, limit), _MAX_CANDIDATE_LIMIT)
