from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

EXPECTED_CHUNK_COUNT = 2
EXPECTED_CANDIDATE_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_upload_rebuild_and_runtime_retrieval_are_explicit(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge.embedding_store import chunk_embedding_store
    from apeiria.ai.knowledge.repository import KnowledgeRepository
    from apeiria.ai.knowledge.service import KnowledgeRetrievalService

    service = KnowledgeRetrievalService(repository=KnowledgeRepository())

    async def scenario() -> None:
        uploaded = await service.upload_document(
            source_file_name="apeiria.md",
            content="# Apeiria\n\nRAG stores chunks for retrieval.",
        )

        assert uploaded.document.chunk_count == EXPECTED_CHUNK_COUNT
        assert uploaded.diagnostics.processed_count == EXPECTED_CHUNK_COUNT
        assert uploaded.diagnostics.failed_count == 0
        for chunk in uploaded.chunks:
            assert chunk_embedding_store.get(chunk_id=chunk.chunk_id) is not None

        deleted_embedding = uploaded.chunks[0]
        assert chunk_embedding_store.delete(chunk_id=deleted_embedding.chunk_id) is True

        runtime_result = await service.retrieve(
            query_text="Apeiria retrieval",
            limit=3,
            mutate_embeddings=False,
        )

        assert runtime_result.diagnostics.missing_embedding_count == 1
        assert chunk_embedding_store.get(chunk_id=deleted_embedding.chunk_id) is None

        rebuild = await service.rebuild_embeddings(
            document_id=uploaded.document.document_id
        )
        assert rebuild.processed_count == EXPECTED_CHUNK_COUNT
        assert (
            chunk_embedding_store.get(chunk_id=deleted_embedding.chunk_id) is not None
        )

    asyncio.run(scenario())


def test_retrieval_preview_returns_ranked_labeled_chunks(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge.repository import KnowledgeRepository
    from apeiria.ai.knowledge.service import KnowledgeRetrievalService

    service = KnowledgeRetrievalService(repository=KnowledgeRepository())

    async def scenario() -> None:
        await service.upload_document(
            source_file_name="rag.txt",
            content="Apeiria RAG retrieval uses chunks.\n\nCooking recipes need salt.",
        )

        result = await service.preview_retrieval(
            query_text="How does Apeiria RAG retrieve chunks?",
            limit=2,
        )

        assert result.diagnostics.candidate_count == EXPECTED_CANDIDATE_COUNT
        assert result.diagnostics.selected_count == EXPECTED_CANDIDATE_COUNT
        assert result.diagnostics.rerank_status in {"not_configured", "applied"}
        assert [item.label for item in result.items] == ["K1", "K2"]
        assert result.items[0].rank == 1
        assert result.items[0].document_id.startswith("kdoc_")
        assert result.items[0].chunk_id.startswith("kchunk_")
        assert result.items[0].title == "rag"
        assert result.items[0].score > 0
        assert "Apeiria RAG retrieval" in result.items[0].excerpt

    asyncio.run(scenario())


def test_retrieval_handles_empty_query_without_failure(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge.repository import KnowledgeRepository
    from apeiria.ai.knowledge.service import KnowledgeRetrievalService

    service = KnowledgeRetrievalService(repository=KnowledgeRepository())

    async def scenario() -> None:
        result = await service.preview_retrieval(query_text=" ", limit=3)

        assert result.items == ()
        assert result.diagnostics.degradation_reason == "empty_query"
        assert result.diagnostics.selected_count == 0
        assert result.diagnostics.candidate_count == 0

    asyncio.run(scenario())


def test_retrieval_uses_optional_rerank_when_configured(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge import service as service_module
    from apeiria.ai.knowledge.repository import KnowledgeRepository
    from apeiria.ai.knowledge.service import KnowledgeRetrievalService
    from apeiria.ai.model.runtime.adapter import (
        AIModelRerankResponse,
        AIModelRerankResultItem,
    )

    async def select_default_model(*, capability_type: str) -> object | None:
        if capability_type == "embedding":
            return None
        if capability_type == "rerank":
            return SimpleNamespace(
                source=SimpleNamespace(source_id="source-1"),
                model=SimpleNamespace(
                    model_id="rerank-model-1",
                    model_identifier="rerank-model",
                ),
            )
        return None

    async def rerank_documents_for_source(**_: object) -> AIModelRerankResponse:
        return AIModelRerankResponse(
            source_id="source-1",
            model_name="rerank-model",
            results=(
                AIModelRerankResultItem(index=1, relevance_score=0.99),
                AIModelRerankResultItem(index=0, relevance_score=0.5),
            ),
        )

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

    service = KnowledgeRetrievalService(repository=KnowledgeRepository())

    async def scenario() -> None:
        await service.upload_document(
            source_file_name="topics.txt",
            content="alpha target paragraph\n\nbeta reranked paragraph",
        )

        result = await service.preview_retrieval(query_text="alpha", limit=2)

        assert result.diagnostics.rerank_status == "applied"
        assert [item.excerpt for item in result.items] == [
            "beta reranked paragraph",
            "alpha target paragraph",
        ]
        assert [item.label for item in result.items] == ["K1", "K2"]

    asyncio.run(scenario())
