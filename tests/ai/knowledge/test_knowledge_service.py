from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


def test_upload_creates_document_and_chunks(tmp_path: Path) -> None:
    async def _run() -> None:
        from sqlalchemy import select

        from apeiria.ai.knowledge.service import upload
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_knowledge import KnowledgeChunk, KnowledgeDocument

        async with async_db(tmp_path / "test.db"):
            doc = await upload(
                title="Test Document",
                source_file_name="test.txt",
                content_text="This is test content for knowledge base.",
            )
            assert doc.id is not None
            assert doc.title == "Test Document"

            async with get_session() as db:
                saved = (
                    await db.execute(
                        select(KnowledgeDocument).where(KnowledgeDocument.id == doc.id)
                    )
                ).scalar_one()
                assert saved.content_hash is not None

                chunks = list(
                    (
                        await db.execute(
                            select(KnowledgeChunk).where(
                                KnowledgeChunk.document_id == doc.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(chunks) >= 1
                assert saved.chunk_count == len(chunks)

    asyncio.run(_run())


def test_retrieve_text_fallback(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.knowledge.service import retrieve, upload

        async with async_db(tmp_path / "test.db"):
            await upload(
                title="Searchable",
                source_file_name="search.txt",
                content_text="The quick brown fox jumps over the lazy dog.",
            )

            results = await retrieve("fox", top_k=5)
            assert len(results) >= 1
            chunk, score = results[0]
            assert "fox" in chunk.content
            assert score == 1.0

    asyncio.run(_run())
