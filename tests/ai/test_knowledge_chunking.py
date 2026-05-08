from __future__ import annotations

import pytest


def test_text_chunking_is_deterministic_and_normalizes_line_endings() -> None:
    from apeiria.ai.knowledge.chunking import chunk_uploaded_document

    first = chunk_uploaded_document(
        source_file_name="notes.txt",
        content=b"Alpha line\r\ncontinues.\r\n\r\nBeta line.",
        max_chunk_chars=40,
        max_chunks=8,
    )
    second = chunk_uploaded_document(
        source_file_name="notes.txt",
        content=b"Alpha line\ncontinues.\n\nBeta line.",
        max_chunk_chars=40,
        max_chunks=8,
    )

    assert first.title == "notes"
    assert first.content_text == "Alpha line\ncontinues.\n\nBeta line."
    assert [chunk.ordinal for chunk in first.chunks] == [0, 1]
    assert [chunk.text for chunk in first.chunks] == [
        "Alpha line\ncontinues.",
        "Beta line.",
    ]
    assert [chunk.chunk_hash for chunk in first.chunks] == [
        chunk.chunk_hash for chunk in second.chunks
    ]
    assert first.content_hash == second.content_hash


def test_markdown_upload_is_accepted_as_bounded_text() -> None:
    from apeiria.ai.knowledge.chunking import chunk_uploaded_document

    result = chunk_uploaded_document(
        source_file_name="guide.md",
        content="# Guide\n\nUse RAG carefully.",
        max_chunk_chars=80,
        max_chunks=8,
    )

    assert result.title == "guide"
    assert result.content_text == "# Guide\n\nUse RAG carefully."
    assert [chunk.text for chunk in result.chunks] == ["# Guide", "Use RAG carefully."]


def test_unsupported_or_oversized_uploads_are_rejected_cleanly() -> None:
    from apeiria.ai.knowledge.chunking import (
        KnowledgeUploadValidationError,
        chunk_uploaded_document,
    )

    with pytest.raises(KnowledgeUploadValidationError, match="unsupported_file_type"):
        chunk_uploaded_document(source_file_name="guide.pdf", content="text")

    with pytest.raises(KnowledgeUploadValidationError, match="document_too_large"):
        chunk_uploaded_document(
            source_file_name="guide.txt",
            content="x" * 11,
            max_document_chars=10,
        )

    with pytest.raises(KnowledgeUploadValidationError, match="too_many_chunks"):
        chunk_uploaded_document(
            source_file_name="guide.md",
            content="one\n\ntwo\n\nthree",
            max_chunk_chars=4,
            max_chunks=2,
        )
