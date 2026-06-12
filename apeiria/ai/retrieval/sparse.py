"""SQLite-backed sparse retrieval fallback."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

from apeiria.ai.retrieval.models import RetrievalCandidate, RetrievalDocument
from apeiria.db.engine import get_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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

    async def upsert_many(self, documents: tuple[RetrievalDocument, ...]) -> None:
        """Upsert searchable document projections into the sparse index."""

        if not documents:
            return
        async with get_session() as session:
            if not await _try_ensure_schema(session):
                return
            for document in documents:
                searchable_title = _indexed_text(document.title or "")
                searchable_body = _indexed_text(document.text)
                await session.execute(
                    text("""
                    DELETE FROM ai_retrieval_sparse_fts
                    WHERE document_id = :document_id
                    """),
                    {"document_id": document.document_id},
                )
                await session.execute(
                    text("""
                    INSERT INTO ai_retrieval_sparse_fts (
                        document_id,
                        domain,
                        title,
                        body,
                        searchable
                    ) VALUES (:document_id, :domain, :title, :body, :searchable)
                    """),
                    {
                        "document_id": document.document_id,
                        "domain": document.domain,
                        "title": searchable_title,
                        "body": searchable_body,
                        "searchable": f"{searchable_title} {searchable_body}".strip(),
                    },
                )
            await session.commit()

    async def delete_many(self, document_ids: tuple[str, ...]) -> None:
        """Delete sparse index rows by retrieval document id."""

        if not document_ids:
            return
        async with get_session() as session:
            if not await _try_ensure_schema(session):
                return
            for document_id in document_ids:
                await session.execute(
                    text("""
                    DELETE FROM ai_retrieval_sparse_fts
                    WHERE document_id = :document_id
                    """),
                    {"document_id": document_id},
                )
            await session.commit()

    async def search(
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
        escaped = [term.replace('"', '""') for term in terms]
        query = " OR ".join(f'"{esc}"' for esc in escaped)
        placeholders = ",".join(f":id_{i}" for i in range(len(document_map)))
        params: dict[str, object] = {
            f"id_{i}": doc_id for i, doc_id in enumerate(document_map.keys())
        }
        params["query"] = query
        params["limit"] = limit
        try:
            async with get_session() as session:
                if not await _try_ensure_schema(session):
                    return _fallback_search(
                        query_terms=terms,
                        documents=documents,
                        limit=limit,
                    )
                result = await session.execute(
                    text(f"""
                    SELECT document_id, bm25(ai_retrieval_sparse_fts) AS rank
                    FROM ai_retrieval_sparse_fts
                    WHERE document_id IN ({placeholders})
                        AND ai_retrieval_sparse_fts MATCH :query
                    ORDER BY rank ASC, rowid ASC
                    LIMIT :limit
                    """),
                    params,
                )
                rows = result.fetchall()
        except Exception:  # noqa: BLE001
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


async def _ensure_schema(session: AsyncSession) -> None:
    await session.execute(
        text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS ai_retrieval_sparse_fts
        USING fts5(
            document_id UNINDEXED,
            domain UNINDEXED,
            title,
            body,
            searchable
        )
        """)
    )
    await session.commit()


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


async def _try_ensure_schema(session: AsyncSession) -> bool:
    try:
        await _ensure_schema(session)
    except Exception:  # noqa: BLE001
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
