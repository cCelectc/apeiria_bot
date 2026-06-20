from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from nonebot.log import logger
from sqlalchemy import select

from apeiria.ai.knowledge.chunking import recursive_split
from apeiria.db.engine import get_session
from apeiria.db.models.ai_knowledge import KnowledgeChunk, KnowledgeDocument

if TYPE_CHECKING:
    from apeiria.ai.embedding.index import VectorIndex

_background_tasks: set[asyncio.Task[None]] = set()
_knowledge_index_instance: VectorIndex | None = None


def _get_knowledge_index(
    dimensions: int = 384,
) -> VectorIndex | None:
    global _knowledge_index_instance  # noqa: PLW0603
    if _knowledge_index_instance is None:
        try:
            from apeiria.ai.embedding.index import VectorIndex

            _knowledge_index_instance = VectorIndex("knowledge", dimensions)
            _knowledge_index_instance.load()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to load knowledge index", exc_info=True)
            return None
    return _knowledge_index_instance


async def upload(
    title: str,
    source_file_name: str,
    content_text: str,
    *,
    embedding_model_id: str | None = None,
) -> KnowledgeDocument:
    content_hash = hashlib.sha256(content_text.encode()).hexdigest()

    async with get_session() as db:
        doc = KnowledgeDocument(
            title=title,
            source_file_name=source_file_name,
            content_hash=content_hash,
            content_text=content_text,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

    chunks_text = recursive_split(content_text)

    async with get_session() as db:
        for i, chunk_text in enumerate(chunks_text):
            chunk = KnowledgeChunk(
                document_id=doc.id,
                content=chunk_text,
                chunk_index=i,
                embedding_model=embedding_model_id,
            )
            db.add(chunk)
        doc_row = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == doc.id)
            )
        ).scalar_one()
        doc_row.chunk_count = len(chunks_text)
        await db.commit()

    if embedding_model_id:
        from apeiria.ai.knowledge.build import embed_pending_chunks

        task = asyncio.create_task(embed_pending_chunks(doc.id, embedding_model_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return doc


async def retrieve(
    query: str,
    *,
    embedding_model_id: str | None = None,
    top_k: int = 5,
    rerank_model_id: str | None = None,
) -> list[tuple[KnowledgeChunk, float]]:
    if not embedding_model_id:
        async with get_session() as db:
            stmt = (
                select(KnowledgeChunk)
                .where(KnowledgeChunk.content.contains(query))
                .limit(top_k)
            )
            chunks = list((await db.execute(stmt)).scalars().all())
            return [(c, 1.0) for c in chunks]

    from apeiria.ai.embedding.embed import embed

    vectors = await embed(embedding_model_id, [query])

    index = _get_knowledge_index()
    if not index or not vectors:
        return []

    results = index.search(vectors[0], top_k=top_k * 2)
    if not results:
        return []

    chunk_ids = [r[0] for r in results]
    scores = {r[0]: r[1] for r in results}

    async with get_session() as db:
        chunks = list(
            (
                await db.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids))
                )
            )
            .scalars()
            .all()
        )

    scored = [(c, scores.get(c.id, 0.0)) for c in chunks]

    if rerank_model_id and scored:
        from apeiria.ai.rerank.rerank import rerank

        docs = [c.content for c, _ in scored]
        rerank_results = await rerank(rerank_model_id, query, docs, top_n=top_k)
        scored = [(scored[r.index][0], r.score) for r in rerank_results]

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
