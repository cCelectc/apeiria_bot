"""Tests for retrieval sparse index and dense scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from apeiria.ai.retrieval.dense import score_dense_candidates
from apeiria.ai.retrieval.identity import content_hash_for_text, retrieval_document_id
from apeiria.ai.retrieval.models import DenseVectorRecord, RetrievalDocument
from apeiria.ai.retrieval.sparse import RetrievalSparseIndex
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


class TestIdentityHelpers:
    def test_document_id_format(self) -> None:
        rid = retrieval_document_id(domain="memory", source_id="mem_abc")
        assert rid == "memory:mem_abc"

    def test_content_hash_is_sha256_hex(self) -> None:
        h = content_hash_for_text("hello", "world")
        assert len(h) == 64  # noqa: PLR2004
        assert h != content_hash_for_text("different")

    def test_content_hash_deterministic(self) -> None:
        a = content_hash_for_text("a", "b")
        b = content_hash_for_text("a", "b")
        assert a == b


class TestDenseScoring:
    def test_scores_and_returns_candidates(self) -> None:
        query = (1.0, 0.0, 0.0)
        docs = (
            RetrievalDocument(
                document_id="d1", domain="memory", text="hello", content_hash="h1"
            ),
            RetrievalDocument(
                document_id="d2", domain="memory", text="world", content_hash="h2"
            ),
        )
        records = (
            DenseVectorRecord(
                document_id="d1",
                embedding_space_id="space1",
                dimension=3,
                vector=(1.0, 0.0, 0.0),
                content_hash="h1",
            ),
            DenseVectorRecord(
                document_id="d2",
                embedding_space_id="space1",
                dimension=3,
                vector=(0.0, 1.0, 0.0),
                content_hash="h2",
            ),
        )
        result = score_dense_candidates(
            query_vector=query,
            documents=docs,
            records=records,
            embedding_space_id="space1",
            limit=2,
        )
        assert len(result.candidates) >= 1
        assert result.candidates[0].channel == "dense"
        assert result.candidates[0].document.document_id == "d1"

    def test_empty_records_produces_no_candidates(self) -> None:
        docs = (
            RetrievalDocument(
                document_id="d1", domain="memory", text="x", content_hash="h"
            ),
        )
        result = score_dense_candidates(
            query_vector=(1.0,),
            documents=docs,
            records=(),
            embedding_space_id="s",
            limit=5,
        )
        assert len(result.candidates) == 0


class TestSparseIndex:
    @pytest.mark.anyio
    async def test_upsert_and_search(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_retrieval.db"
        async with async_db(db_path):
            idx = RetrievalSparseIndex()
            doc = RetrievalDocument(
                document_id="test:1",
                domain="memory",
                text="hello world",
                content_hash="abc",
            )
            await idx.upsert_many((doc,))
            result = await idx.search(query_text="hello", documents=(doc,), limit=5)
            assert len(result.candidates) >= 1
            assert result.candidates[0].channel == "sparse"

    @pytest.mark.anyio
    async def test_delete_removes_document(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test_retrieval.db"
        async with async_db(db_path):
            idx = RetrievalSparseIndex()
            doc = RetrievalDocument(
                document_id="test:2",
                domain="memory",
                text="xyzzy",
                content_hash="xyz",
            )
            await idx.upsert_many((doc,))
            await idx.delete_many(("test:2",))
            result = await idx.search(query_text="xyzzy", documents=(doc,), limit=5)
            assert len(result.candidates) == 0
