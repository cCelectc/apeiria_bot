from __future__ import annotations

import asyncio

from nonebot.log import logger
from sqlalchemy import select

from apeiria.db.engine import get_session
from apeiria.db.models.ai_knowledge import KnowledgeChunk, KnowledgeDocument

_background_tasks: set[asyncio.Task[None]] = set()
_EMBED_TIMEOUT = 300


async def embed_pending_chunks(
    document_id: int,
    embedding_model_id: str,
) -> None:
    from apeiria.ai.embedding.embed import embed

    async with get_session() as db:
        chunks = list(
            (
                await db.execute(
                    select(KnowledgeChunk)
                    .where(
                        KnowledgeChunk.document_id == document_id,
                        KnowledgeChunk.embedding_status == "pending",
                    )
                    .order_by(KnowledgeChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )

    if not chunks:
        return

    failed_count = 0
    for chunk in chunks:
        try:
            vectors = await asyncio.wait_for(
                embed(embedding_model_id, [chunk.content]),
                timeout=_EMBED_TIMEOUT,
            )
            async with get_session() as db:
                c = (
                    await db.execute(
                        select(KnowledgeChunk).where(KnowledgeChunk.id == chunk.id)
                    )
                ).scalar_one()
                c.embedding_status = "embedded"
                c.embedding_model = embedding_model_id
                await db.commit()
            from apeiria.ai.knowledge.service import (
                _get_knowledge_index,
            )

            index = _get_knowledge_index()
            if index and vectors:
                index.add([chunk.id], vectors)
        except Exception:  # noqa: BLE001, PERF203
            failed_count += 1
            logger.warning(
                "Failed to embed chunk %d",
                chunk.id,
                exc_info=True,
            )
            async with get_session() as db:
                c = (
                    await db.execute(
                        select(KnowledgeChunk).where(KnowledgeChunk.id == chunk.id)
                    )
                ).scalar_one()
                c.embedding_status = "failed"
                await db.commit()

    async with get_session() as db:
        doc = (
            await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
            )
        ).scalar_one_or_none()
        if doc:
            if failed_count > 0:
                doc.status = "degraded"
            elif failed_count == len(chunks):
                doc.status = "failed"
            else:
                doc.status = "embedded"
            await db.commit()


async def resume_pending() -> None:
    async with get_session() as db:
        pending_docs = list(
            (
                await db.execute(
                    select(KnowledgeChunk.document_id)
                    .where(KnowledgeChunk.embedding_status == "pending")
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

    for doc_id in pending_docs:
        async with get_session() as db:
            model = (
                await db.execute(
                    select(KnowledgeChunk.embedding_model)
                    .where(
                        KnowledgeChunk.document_id == doc_id,
                        KnowledgeChunk.embedding_model.isnot(None),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
        if model:
            task = asyncio.create_task(embed_pending_chunks(doc_id, model))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
