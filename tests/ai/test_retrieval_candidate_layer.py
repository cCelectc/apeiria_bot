from __future__ import annotations

import asyncio
import sqlite3
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

_RERANK_FAILURE_MESSAGE = "rerank unavailable"
_FTS_FAILURE_MESSAGE = "fts5 unavailable"

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_sparse_fallback_handles_chinese_without_embedding(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.retrieval.models import RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    async def select_default_model(*, capability_type: str) -> object | None:
        del capability_type
        return None

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )

    documents = (
        RetrievalDocument(
            document_id="memory:genshin",
            domain="memory",
            text="晚上原神多人联机",
            content_hash="hash-genshin",
        ),
        RetrievalDocument(
            document_id="memory:cooking",
            domain="memory",
            text="周末准备烤面包",
            content_hash="hash-cooking",
        ),
    )
    sparse_index = RetrievalSparseIndex()
    sparse_index.upsert_many(documents)
    service = RetrievalCandidateService(sparse_index=sparse_index)

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="原神联机",
            documents=documents,
            limit=1,
            allow_rerank=False,
        )

        assert result.diagnostics.path == "sparse"
        assert result.candidates[0].document.document_id == "memory:genshin"

    asyncio.run(scenario())


def test_sparse_search_does_not_index_during_query(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.retrieval.models import RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    async def select_default_model(*, capability_type: str) -> object | None:
        del capability_type
        return None

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )

    documents = (
        RetrievalDocument(
            document_id="memory:unindexed",
            domain="memory",
            text="原神联机",
            content_hash="hash-unindexed",
        ),
    )
    service = RetrievalCandidateService(sparse_index=RetrievalSparseIndex())

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="原神联机",
            documents=documents,
            limit=1,
            allow_rerank=False,
        )

        assert result.diagnostics.path == "sparse"
        assert result.candidates == ()

    asyncio.run(scenario())


def test_sparse_search_uses_in_memory_ngram_fallback_when_fts_unavailable(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.retrieval import sparse as sparse_module
    from apeiria.ai.retrieval.models import RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    async def select_default_model(*, capability_type: str) -> object | None:
        del capability_type
        return None

    def fail_schema(_: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError(_FTS_FAILURE_MESSAGE)

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )
    monkeypatch.setattr(sparse_module, "_ensure_schema", fail_schema)

    documents = (
        RetrievalDocument(
            document_id="knowledge:target",
            domain="knowledge",
            title="旅行计划",
            text="上海周末美术馆路线",
            content_hash="hash-target",
        ),
        RetrievalDocument(
            document_id="knowledge:other",
            domain="knowledge",
            title="烘焙记录",
            text="面包发酵温度",
            content_hash="hash-other",
        ),
    )
    service = RetrievalCandidateService(sparse_index=RetrievalSparseIndex())

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="上海美术馆",
            documents=documents,
            limit=1,
            allow_rerank=False,
        )

        assert result.diagnostics.path == "sparse"
        assert result.diagnostics.fallback_reason == "sparse_backend_unavailable"
        assert result.candidates[0].document.document_id == "knowledge:target"

    asyncio.run(scenario())


def test_dense_space_mismatch_falls_back_to_sparse(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.model.runtime.adapter import AIModelEmbeddingResponse
    from apeiria.ai.retrieval.models import DenseVectorRecord, RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    selected = _selected_embedding_model()

    async def select_default_model(*, capability_type: str) -> object | None:
        return selected if capability_type == "embedding" else None

    async def embed_texts_for_source(**_: object) -> AIModelEmbeddingResponse:
        return AIModelEmbeddingResponse(
            source_id=selected.source.source_id,
            model_name=selected.model.model_identifier,
            vectors=((1.0, 0.0),),
        )

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )
    monkeypatch.setattr(
        service_module.ai_source_service,
        "get_source_api_key",
        lambda _: "key",
    )
    monkeypatch.setattr(
        service_module.model_invoker,
        "embed_texts_for_source",
        embed_texts_for_source,
    )

    documents = (
        RetrievalDocument(
            document_id="knowledge:target",
            domain="knowledge",
            title="Apeiria Retrieval",
            text="embedding search should fall back safely",
            content_hash="hash-target",
        ),
    )
    sparse_index = RetrievalSparseIndex()
    sparse_index.upsert_many(documents)
    service = RetrievalCandidateService(sparse_index=sparse_index)

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="embedding fallback",
            documents=documents,
            limit=1,
            allow_rerank=False,
            dense_records=(
                DenseVectorRecord(
                    document_id="knowledge:target",
                    embedding_space_id="other-space",
                    dimension=2,
                    vector=(1.0, 0.0),
                    content_hash="hash-target",
                ),
            ),
        )

        assert result.diagnostics.path == "sparse"
        assert result.diagnostics.fallback_reason == "no_comparable_dense_vectors"
        assert result.diagnostics.stale_embedding_count == 1
        assert result.candidates[0].document.document_id == "knowledge:target"

    asyncio.run(scenario())


def test_rerank_failure_preserves_sparse_order(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.retrieval.models import RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    selected = _selected_rerank_model()

    async def select_default_model(*, capability_type: str) -> object | None:
        if capability_type == "embedding":
            return None
        if capability_type == "rerank":
            return selected
        return None

    async def rerank_documents_for_source(**_: object) -> object:
        raise RuntimeError(_RERANK_FAILURE_MESSAGE)

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )
    monkeypatch.setattr(
        service_module.ai_source_service,
        "get_source_api_key",
        lambda _: "key",
    )
    monkeypatch.setattr(
        service_module.model_invoker,
        "rerank_documents_for_source",
        rerank_documents_for_source,
    )

    documents = (
        RetrievalDocument(
            document_id="knowledge:first",
            domain="knowledge",
            text="alpha target",
            content_hash="hash-first",
        ),
        RetrievalDocument(
            document_id="knowledge:second",
            domain="knowledge",
            text="alpha secondary",
            content_hash="hash-second",
        ),
    )
    sparse_index = RetrievalSparseIndex()
    sparse_index.upsert_many(documents)
    service = RetrievalCandidateService(sparse_index=sparse_index)

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="alpha",
            documents=documents,
            limit=2,
            allow_rerank=True,
        )

        assert result.diagnostics.path == "sparse"
        assert result.diagnostics.rerank_status == "failed"
        assert [item.document.document_id for item in result.candidates] == [
            "knowledge:first",
            "knowledge:second",
        ]

    asyncio.run(scenario())


def test_invalid_rerank_response_preserves_original_order(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.model.runtime.adapter import (
        AIModelRerankResponse,
        AIModelRerankResultItem,
    )
    from apeiria.ai.retrieval.models import RetrievalDocument
    from apeiria.ai.retrieval.service import RetrievalCandidateService
    from apeiria.ai.retrieval.sparse import RetrievalSparseIndex

    selected = _selected_rerank_model()

    async def select_default_model(*, capability_type: str) -> object | None:
        if capability_type == "embedding":
            return None
        if capability_type == "rerank":
            return selected
        return None

    async def rerank_documents_for_source(**_: object) -> AIModelRerankResponse:
        return AIModelRerankResponse(
            source_id=selected.source.source_id,
            model_name=selected.model.model_identifier,
            results=(
                AIModelRerankResultItem(index=99, relevance_score=1.0),
                AIModelRerankResultItem(index=1, relevance_score=0.9),
            ),
        )

    from apeiria.ai.retrieval import service as service_module

    monkeypatch.setattr(
        service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )
    monkeypatch.setattr(
        service_module.ai_source_service,
        "get_source_api_key",
        lambda _: "key",
    )
    monkeypatch.setattr(
        service_module.model_invoker,
        "rerank_documents_for_source",
        rerank_documents_for_source,
    )

    documents = (
        RetrievalDocument(
            document_id="knowledge:first",
            domain="knowledge",
            text="alpha target",
            content_hash="hash-first",
        ),
        RetrievalDocument(
            document_id="knowledge:second",
            domain="knowledge",
            text="alpha secondary",
            content_hash="hash-second",
        ),
    )
    sparse_index = RetrievalSparseIndex()
    sparse_index.upsert_many(documents)
    service = RetrievalCandidateService(sparse_index=sparse_index)

    async def scenario() -> None:
        result = await service.retrieve_candidates(
            query_text="alpha",
            documents=documents,
            limit=2,
            allow_rerank=True,
        )

        assert result.diagnostics.rerank_status == "failed"
        assert [item.document.document_id for item in result.candidates] == [
            "knowledge:first",
            "knowledge:second",
        ]

    asyncio.run(scenario())


def _selected_embedding_model() -> SimpleNamespace:
    return SimpleNamespace(
        source=SimpleNamespace(
            source_id="source-embedding",
            adapter_kind="openai_compatible",
            client_type="openai",
        ),
        model=SimpleNamespace(
            model_id="embedding-model-id",
            model_identifier="embedding-model",
        ),
    )


def _selected_rerank_model() -> SimpleNamespace:
    return SimpleNamespace(
        source=SimpleNamespace(source_id="source-rerank"),
        model=SimpleNamespace(
            model_id="rerank-model-id",
            model_identifier="rerank-model",
        ),
    )
