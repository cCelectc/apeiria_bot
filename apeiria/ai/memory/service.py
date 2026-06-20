from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from nonebot.log import logger
from sqlalchemy import select

from apeiria.db.base import _now_iso
from apeiria.db.engine import get_session
from apeiria.db.models.ai_memory import Fact

if TYPE_CHECKING:
    from apeiria.ai.embedding.index import VectorIndex
    from apeiria.db.models.ai_settings import AIRuntimeSettings

_DEDUP_THRESHOLD = 0.85
_SECONDS_PER_DAY = 86400


async def remember(
    user_id: str,
    session_id: str,
    content: str,
    importance: float = 0.5,
    *,
    embedding_model_id: str | None = None,
) -> Fact:
    existing = await _similarity_dedup(
        user_id, session_id, content, embedding_model_id=embedding_model_id
    )
    if existing:
        async with get_session() as db:
            existing.content = content
            existing.importance = importance
            existing.last_reinforced_at = _now_iso()
            db.add(existing)
            await db.commit()
            return existing

    async with get_session() as db:
        fact = Fact(
            user_id=user_id,
            session_id=session_id,
            content=content,
            importance=importance,
            last_reinforced_at=_now_iso(),
        )
        db.add(fact)
        await db.commit()
        await db.refresh(fact)

    if embedding_model_id:
        try:
            from apeiria.ai.embedding.embed import embed

            vectors = await embed(embedding_model_id, [content])
            index = _get_facts_index()
            if index and vectors:
                index.add([fact.id], vectors)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to embed fact {}", fact.id, exc_info=True)

    return fact


async def search(  # noqa: PLR0913
    user_id: str,
    session_id: str,
    query: str,
    *,
    settings: AIRuntimeSettings,
    embedding_model_id: str | None = None,
    top_k: int = 10,
) -> list[Fact]:
    facts: list[Fact] = []

    if embedding_model_id:
        try:
            from apeiria.ai.embedding.embed import embed

            vectors = await embed(embedding_model_id, [query])
            index = _get_facts_index()
            if index and vectors:
                results = index.search(vectors[0], top_k=top_k * 3)
                fact_ids = [r[0] for r in results]
                if fact_ids:
                    async with get_session() as db:
                        stmt = select(Fact).where(Fact.id.in_(fact_ids))
                        if settings.memory_isolate_by_session:
                            stmt = stmt.where(
                                Fact.user_id == user_id,
                                Fact.session_id == session_id,
                            )
                        else:
                            stmt = stmt.where(Fact.user_id == user_id)
                        facts = list((await db.execute(stmt)).scalars().all())
        except Exception:  # noqa: BLE001
            logger.warning(
                "Embedding search failed, falling back to text",
                exc_info=True,
            )

    if not facts:
        async with get_session() as db:
            stmt = select(Fact).where(
                Fact.user_id == user_id,
                Fact.content.contains(query),
            )
            if settings.memory_isolate_by_session:
                stmt = stmt.where(Fact.session_id == session_id)
            facts = list((await db.execute(stmt.limit(top_k))).scalars().all())

    now = datetime.now(timezone.utc)
    async with get_session() as db:
        for fact in facts:
            last = datetime.fromisoformat(fact.last_reinforced_at)
            age_days = (now - last).total_seconds() / _SECONDS_PER_DAY
            if age_days > 0:
                decay_factor = 0.5 ** (age_days / settings.memory_half_life_days)
                effective = fact.importance * decay_factor
                floor = fact.importance * settings.memory_floor_ratio
                fact.importance = max(floor, effective)
                db.add(fact)
        await db.commit()

    facts.sort(key=lambda f: f.importance, reverse=True)
    return facts[:top_k]


async def _similarity_dedup(
    user_id: str,
    session_id: str,
    content: str,
    *,
    embedding_model_id: str | None = None,
) -> Fact | None:
    if not embedding_model_id:
        return None
    try:
        from apeiria.ai.embedding.embed import embed

        vectors = await embed(embedding_model_id, [content])
        index = _get_facts_index()
        if not index or not vectors:
            return None
        results = index.search(vectors[0], top_k=5)
        if not results:
            return None
        candidate_ids = [r[0] for r in results if r[1] > _DEDUP_THRESHOLD]
        if not candidate_ids:
            return None
        async with get_session() as db:
            stmt = select(Fact).where(
                Fact.id.in_(candidate_ids),
                Fact.user_id == user_id,
                Fact.session_id == session_id,
            )
            return (await db.execute(stmt)).scalars().first()
    except Exception:  # noqa: BLE001
        logger.warning("Dedup check failed", exc_info=True)
        return None


_facts_index_instance: VectorIndex | None = None


def _get_facts_index(dimensions: int = 384) -> VectorIndex | None:
    global _facts_index_instance  # noqa: PLW0603
    if _facts_index_instance is None:
        try:
            from apeiria.ai.embedding.index import VectorIndex

            _facts_index_instance = VectorIndex("facts", dimensions)
            _facts_index_instance.load()
        except Exception:  # noqa: BLE001
            logger.warning("Failed to load facts index", exc_info=True)
            return None
    return _facts_index_instance
