"""SQLite-backed sparse retrieval fallback."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass

from apeiria.ai.retrieval.models import RetrievalCandidate, RetrievalDocument
from apeiria.db.runtime import database_runtime

_MAX_TERMS = 24
_ASCII_NGRAM_MIN_LENGTH = 4
_CJK_WHOLE_TERM_MAX_LENGTH = 8
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


@dataclass(frozen=True)
class SparseSearchResult:
    """Sparse candidates returned by the fallback index."""

    candidates: tuple[RetrievalCandidate, ...]
    used_fallback: bool = False


class RetrievalSparseIndex:
    """Own the local sparse retrieval index."""

    def upsert_many(self, documents: tuple[RetrievalDocument, ...]) -> None:
        """Upsert searchable document projections into the sparse index."""

        if not documents:
            return
        with database_runtime.connect_sync() as connection:
            if not _try_ensure_schema(connection):
                return
            for document in documents:
                searchable_title = _indexed_text(document.title or "")
                searchable_body = _indexed_text(document.text)
                connection.execute(
                    """
                    DELETE FROM ai_retrieval_sparse_fts
                    WHERE document_id = ?
                    """,
                    (document.document_id,),
                )
                connection.execute(
                    """
                    INSERT INTO ai_retrieval_sparse_fts (
                        document_id,
                        domain,
                        title,
                        body,
                        searchable
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document.document_id,
                        document.domain,
                        searchable_title,
                        searchable_body,
                        f"{searchable_title} {searchable_body}".strip(),
                    ),
                )

    def delete_many(self, document_ids: tuple[str, ...]) -> None:
        """Delete sparse index rows by retrieval document id."""

        if not document_ids:
            return
        with database_runtime.connect_sync() as connection:
            if not _try_ensure_schema(connection):
                return
            for document_id in document_ids:
                connection.execute(
                    """
                    DELETE FROM ai_retrieval_sparse_fts
                    WHERE document_id = ?
                    """,
                    (document_id,),
                )

    def search(
        self,
        *,
        query_text: str,
        documents: tuple[RetrievalDocument, ...],
        limit: int,
    ) -> SparseSearchResult:
        """Return sparse candidates limited to the provided documents."""

        if limit <= 0 or not query_text.strip() or not documents:
            return SparseSearchResult(candidates=())
        terms = _search_terms(query_text)
        if not terms:
            return SparseSearchResult(candidates=())
        document_map = {document.document_id: document for document in documents}
        query = " OR ".join(f'"{term}"' for term in terms)
        placeholders = ",".join("?" for _ in document_map)
        try:
            with database_runtime.connect_sync() as connection:
                if not _try_ensure_schema(connection):
                    return _fallback_search(
                        query_terms=terms,
                        documents=documents,
                        limit=limit,
                    )
                rows = connection.execute(
                    f"""
                    SELECT document_id, bm25(ai_retrieval_sparse_fts) AS rank
                    FROM ai_retrieval_sparse_fts
                    WHERE document_id IN ({placeholders})
                        AND ai_retrieval_sparse_fts MATCH ?
                    ORDER BY rank ASC, rowid ASC
                    LIMIT ?
                    """,
                    (*document_map.keys(), query, limit),
                ).fetchall()
        except sqlite3.Error:
            return _fallback_search(
                query_terms=terms,
                documents=documents,
                limit=limit,
            )

        candidates: list[RetrievalCandidate] = []
        for index, row in enumerate(rows):
            document = document_map.get(str(row[0]))
            if document is None:
                continue
            rank_value = float(row[1])
            candidates.append(
                RetrievalCandidate(
                    document=document,
                    channel="sparse",
                    score=-rank_value,
                    rank=index + 1,
                    matched_fields=("title", "text") if document.title else ("text",),
                )
            )
        return SparseSearchResult(candidates=tuple(candidates))


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS ai_retrieval_sparse_fts
        USING fts5(
            document_id UNINDEXED,
            domain UNINDEXED,
            title,
            body,
            searchable
        )
        """
    )


def _fallback_search(
    *,
    query_terms: tuple[str, ...],
    documents: tuple[RetrievalDocument, ...],
    limit: int,
) -> SparseSearchResult:
    query_set = set(query_terms)
    scored: list[tuple[float, int, RetrievalDocument]] = []
    for ordinal, document in enumerate(documents):
        title_terms = set(_search_terms(document.title or ""))
        body_terms = set(_search_terms(document.text))
        title_overlap = len(query_set & title_terms)
        body_overlap = len(query_set & body_terms)
        score = float(title_overlap * 2 + body_overlap)
        if score <= 0:
            continue
        scored.append((score, -ordinal, document))
    scored.sort(reverse=True)
    candidates = tuple(
        RetrievalCandidate(
            document=document,
            channel="sparse",
            score=score,
            rank=index + 1,
            matched_fields=("title", "text") if document.title else ("text",),
        )
        for index, (score, _, document) in enumerate(scored[:limit])
    )
    return SparseSearchResult(candidates=candidates, used_fallback=True)


def _try_ensure_schema(connection: sqlite3.Connection) -> bool:
    try:
        _ensure_schema(connection)
    except sqlite3.Error:
        return False
    return True


def _indexed_text(text: str) -> str:
    return " ".join(_search_terms(text))


def _search_terms(text: str) -> tuple[str, ...]:  # noqa: C901
    normalized = unicodedata.normalize("NFKC", text).lower()
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        if value and value not in seen:
            seen.add(value)
            terms.append(value)

    for match in _ASCII_WORD_RE.finditer(normalized):
        word = match.group(0)
        add(word)
        if len(word) >= _ASCII_NGRAM_MIN_LENGTH:
            for index in range(len(word) - 2):
                add(word[index : index + 3])

    for match in _CJK_RE.finditer(normalized):
        chunk = match.group(0)
        if len(chunk) <= _CJK_WHOLE_TERM_MAX_LENGTH:
            add(chunk)
        for size in (2, 3):
            if len(chunk) >= size:
                for index in range(len(chunk) - size + 1):
                    add(chunk[index : index + size])

    return tuple(terms[:_MAX_TERMS])


retrieval_sparse_index = RetrievalSparseIndex()
