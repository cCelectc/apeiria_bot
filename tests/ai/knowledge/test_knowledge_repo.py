"""Tests for knowledge repository CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from apeiria.ai.knowledge.models import KnowledgeDocumentCreate
from apeiria.ai.knowledge.repository import KnowledgeRepository
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.anyio
async def test_create_document(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        doc = await repo.create_document(
            KnowledgeDocumentCreate(
                title="Test Doc",
                source_file_name="test.txt",
                content_text="hello world",
                content_hash="abc123",
                chunks=(("hash1", "chunk text content"),),
            )
        )
        assert doc.document_id.startswith("kdoc_")
        assert doc.title == "Test Doc"
        assert doc.status == "pending"


@pytest.mark.anyio
async def test_list_documents(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        await repo.create_document(
            KnowledgeDocumentCreate(
                title="Doc1",
                source_file_name="a.txt",
                content_text="a",
                content_hash="h1",
                chunks=(("c1", "chunk1"),),
            )
        )
        await repo.create_document(
            KnowledgeDocumentCreate(
                title="Doc2",
                source_file_name="b.txt",
                content_text="b",
                content_hash="h2",
                chunks=(("c2", "chunk2"),),
            )
        )
        docs = await repo.list_documents()
        assert len(docs) == 2  # noqa: PLR2004


@pytest.mark.anyio
async def test_get_document_by_id(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        created = await repo.create_document(
            KnowledgeDocumentCreate(
                title="Doc",
                source_file_name="f.txt",
                content_text="text",
                content_hash="h",
                chunks=(("c1", "chunk"),),
            )
        )
        found = await repo.get_document(document_id=created.document_id)
        assert found is not None
        assert found.document_id == created.document_id


@pytest.mark.anyio
async def test_list_chunks(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        doc = await repo.create_document(
            KnowledgeDocumentCreate(
                title="Doc",
                source_file_name="f.txt",
                content_text="text",
                content_hash="h",
                chunks=(
                    ("c1", "first chunk"),
                    ("c2", "second chunk"),
                ),
            )
        )
        chunks = await repo.list_chunks(document_id=doc.document_id)
        assert len(chunks) == 2  # noqa: PLR2004
        assert chunks[0].chunk_hash in ("c1", "c2")


@pytest.mark.anyio
async def test_delete_document(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        doc = await repo.create_document(
            KnowledgeDocumentCreate(
                title="To Delete",
                source_file_name="d.txt",
                content_text="data",
                content_hash="h",
                chunks=(("c1", "chunk"),),
            )
        )
        deleted = await repo.delete_document(document_id=doc.document_id)
        assert deleted is True
        assert await repo.get_document(document_id=doc.document_id) is None


@pytest.mark.anyio
async def test_mark_document_status(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        repo = KnowledgeRepository()
        doc = await repo.create_document(
            KnowledgeDocumentCreate(
                title="Status Test",
                source_file_name="s.txt",
                content_text="text",
                content_hash="h",
                chunks=(("c1", "chunk"),),
            )
        )
        await repo.mark_document_status(
            document_id=doc.document_id,
            status="embedded",
            last_error=None,
        )
        updated = await repo.get_document(document_id=doc.document_id)
        assert updated is not None
        assert updated.status == "embedded"
