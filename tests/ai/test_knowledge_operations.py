from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

EXPECTED_CHUNK_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_knowledge_operations_cover_management_workflow(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.app.ai.operations import AIOperationsEntry

    operations = AIOperationsEntry()

    async def scenario() -> None:
        initial_state = await operations.get_knowledge_state()
        assert initial_state.rag_enabled is False
        assert initial_state.document_count == 0

        enabled_state = await operations.set_knowledge_rag_enabled(enabled=True)
        assert enabled_state.rag_enabled is True

        upload = await operations.upload_knowledge_document(
            source_file_name="guide.md",
            content="# Guide\n\nApeiria RAG retrieves chunks.",
            actor_username="admin",
        )
        assert upload.document.title == "guide"
        assert upload.diagnostics.processed_count == 0
        assert upload.diagnostics.skipped_count == EXPECTED_CHUNK_COUNT

        listed = await operations.list_knowledge_documents()
        assert [item.document_id for item in listed] == [upload.document.document_id]

        chunks = await operations.list_knowledge_chunks(
            document_id=upload.document.document_id
        )
        assert len(chunks) == EXPECTED_CHUNK_COUNT

        preview = await operations.preview_knowledge_retrieval(
            query_text="Apeiria RAG",
            limit=1,
        )
        assert [item.label for item in preview.items] == ["K1"]

        rebuild = await operations.rebuild_knowledge_embeddings(
            document_id=upload.document.document_id,
            actor_username="admin",
        )
        assert rebuild.processed_count == 0
        assert rebuild.skipped_count == EXPECTED_CHUNK_COUNT

        deleted = await operations.delete_knowledge_document(
            document_id=upload.document.document_id,
            actor_username="admin",
        )
        assert deleted is True
        assert await operations.list_knowledge_documents() == []

    asyncio.run(scenario())
