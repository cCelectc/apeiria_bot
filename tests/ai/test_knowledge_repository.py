from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

EXPECTED_CHUNK_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_default_knowledge_documents_and_chunks_use_sqlite(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge.models import KnowledgeDocumentCreate
    from apeiria.ai.knowledge.repository import KnowledgeRepository

    repository = KnowledgeRepository()
    created = repository.create_document(
        KnowledgeDocumentCreate(
            title="Project Notes",
            source_file_name="notes.md",
            content_text="Alpha paragraph.\n\nBeta paragraph.",
            content_hash="hash-doc-1",
            chunks=(
                ("hash-chunk-1", "Alpha paragraph."),
                ("hash-chunk-2", "Beta paragraph."),
            ),
        )
    )

    assert created.document_id.startswith("kdoc_")
    assert created.title == "Project Notes"
    assert created.source_file_name == "notes.md"
    assert created.status == "pending"
    assert created.chunk_count == EXPECTED_CHUNK_COUNT
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None

    listed = repository.list_documents()
    assert [item.document_id for item in listed] == [created.document_id]

    chunks = repository.list_chunks(document_id=created.document_id)
    assert [chunk.ordinal for chunk in chunks] == [0, 1]
    assert [chunk.chunk_hash for chunk in chunks] == [
        "hash-chunk-1",
        "hash-chunk-2",
    ]
    assert chunks[0].chunk_id.startswith(f"kchunk_{created.document_id}_")
    assert chunks[0].text == "Alpha paragraph."
    assert chunks[0].embedding_status == "missing"

    repository.mark_chunk_embeddings(
        document_id=created.document_id,
        chunk_ids=[chunk.chunk_id for chunk in chunks],
        embedding_model="local_bigrams_v1",
        status="embedded",
    )

    refreshed_chunks = repository.list_chunks(document_id=created.document_id)
    assert {chunk.embedding_model for chunk in refreshed_chunks} == {"local_bigrams_v1"}
    assert {chunk.embedding_status for chunk in refreshed_chunks} == {"embedded"}

    assert repository.delete_document(document_id=created.document_id) is True
    assert repository.get_document(document_id=created.document_id) is None
    assert repository.list_chunks(document_id=created.document_id) == []


def test_default_knowledge_document_update_replaces_chunks(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.knowledge.models import KnowledgeDocumentCreate
    from apeiria.ai.knowledge.repository import KnowledgeRepository

    repository = KnowledgeRepository()
    created = repository.create_document(
        KnowledgeDocumentCreate(
            title="Runbook",
            source_file_name="runbook.txt",
            content_text="old text",
            content_hash="old-hash",
            chunks=(("old-chunk", "old text"),),
        )
    )
    old_chunk_id = repository.list_chunks(document_id=created.document_id)[0].chunk_id

    updated = repository._replace_document_content(
        document_id=created.document_id,
        create_input=KnowledgeDocumentCreate(
            title="Runbook v2",
            source_file_name="runbook.txt",
            content_text="new text\n\nmore text",
            content_hash="new-hash",
            chunks=(("new-chunk-1", "new text"), ("new-chunk-2", "more text")),
        ),
    )

    assert updated is not None
    assert updated.document_id == created.document_id
    assert updated.title == "Runbook v2"
    assert updated.content_hash == "new-hash"
    assert updated.chunk_count == EXPECTED_CHUNK_COUNT

    chunks = repository.list_chunks(document_id=created.document_id)
    assert old_chunk_id not in {chunk.chunk_id for chunk in chunks}
    assert [chunk.text for chunk in chunks] == ["new text", "more text"]
    assert {chunk.embedding_status for chunk in chunks} == {"missing"}
