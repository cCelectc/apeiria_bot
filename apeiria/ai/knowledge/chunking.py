"""Deterministic chunking for default knowledge-base uploads."""

from __future__ import annotations

import hashlib
from pathlib import PurePath

from apeiria.ai.knowledge.models import (
    KnowledgeUploadedChunk,
    KnowledgeUploadedDocument,
)

SUPPORTED_EXTENSIONS = {".txt", ".md"}
DEFAULT_MAX_DOCUMENT_CHARS = 200_000
DEFAULT_MAX_CHUNK_CHARS = 1_200
DEFAULT_MAX_CHUNKS = 256


class KnowledgeUploadValidationError(ValueError):
    """Raised when an uploaded knowledge document cannot be ingested."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def chunk_uploaded_document(
    *,
    source_file_name: str,
    content: str | bytes,
    max_document_chars: int = DEFAULT_MAX_DOCUMENT_CHARS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> KnowledgeUploadedDocument:
    """Normalize and split a text or Markdown upload into stable chunks."""

    suffix = PurePath(source_file_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise KnowledgeUploadValidationError("unsupported_file_type")

    text = _decode_content(content)
    normalized = _normalize_text(text)
    if not normalized:
        raise KnowledgeUploadValidationError("empty_document")
    if len(normalized) > max_document_chars:
        raise KnowledgeUploadValidationError("document_too_large")

    chunk_texts = _split_chunks(normalized, max_chunk_chars=max_chunk_chars)
    if len(chunk_texts) > max_chunks:
        raise KnowledgeUploadValidationError("too_many_chunks")

    chunks = tuple(
        KnowledgeUploadedChunk(
            ordinal=index,
            chunk_hash=_hash_text(chunk_text),
            text=chunk_text,
        )
        for index, chunk_text in enumerate(chunk_texts)
    )
    return KnowledgeUploadedDocument(
        title=_title_from_file_name(source_file_name),
        source_file_name=source_file_name,
        content_text=normalized,
        content_hash=_hash_text(normalized),
        chunks=chunks,
    )


def _decode_content(content: str | bytes) -> str:
    if isinstance(content, str):
        return content
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeUploadValidationError("invalid_encoding") from exc


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _split_chunks(text: str, *, max_chunk_chars: int) -> list[str]:
    if max_chunk_chars <= 0:
        raise KnowledgeUploadValidationError("invalid_chunk_limit")

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chunk_chars:
            chunks.append(paragraph)
            continue
        chunks.extend(_split_long_paragraph(paragraph, max_chunk_chars=max_chunk_chars))
    return chunks


def _split_long_paragraph(paragraph: str, *, max_chunk_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in paragraph.split("\n"):
        candidate = line.strip()
        if not candidate:
            continue
        if not current:
            current = candidate
            continue
        joined = f"{current}\n{candidate}"
        if len(joined) <= max_chunk_chars:
            current = joined
        else:
            chunks.extend(_split_by_width(current, max_chunk_chars=max_chunk_chars))
            current = candidate
    if current:
        chunks.extend(_split_by_width(current, max_chunk_chars=max_chunk_chars))
    return chunks


def _split_by_width(text: str, *, max_chunk_chars: int) -> list[str]:
    return [
        text[index : index + max_chunk_chars].strip()
        for index in range(0, len(text), max_chunk_chars)
        if text[index : index + max_chunk_chars].strip()
    ]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _title_from_file_name(source_file_name: str) -> str:
    stem = PurePath(source_file_name).stem.strip()
    return stem or source_file_name
