from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.model.registry import get_provider
from apeiria.db.engine import get_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from apeiria.ai.types import RerankResult, StreamEvent

_TABLE_WHITELIST = frozenset(
    {
        "ai_chat_models",
        "ai_embedding_models",
        "ai_rerank_models",
    }
)


async def _resolve_adapter(model_table: str, model_id: str) -> tuple[str, Any]:
    if model_table not in _TABLE_WHITELIST:
        msg = f"Invalid model table: {model_table}"
        raise ValueError(msg)

    from sqlalchemy import text as sa_text

    async with get_session() as session:
        row = (
            await session.execute(
                sa_text(
                    f"SELECT source_id FROM {model_table}"
                    " WHERE model_id = :mid AND enabled = 1"
                ),
                {"mid": model_id},
            )
        ).first()
        if not row:
            from apeiria.ai.model.exceptions import AIModelNotFoundError

            raise AIModelNotFoundError(model_id)
        source_id = row[0]
        source_row = (
            await session.execute(
                sa_text(
                    "SELECT adapter FROM ai_sources"
                    " WHERE source_id = :sid AND enabled = 1"
                ),
                {"sid": source_id},
            )
        ).first()
        if not source_row:
            from apeiria.ai.model.exceptions import AIModelSourceNotFoundError

            raise AIModelSourceNotFoundError(source_id)
        return source_row[0], row


async def stream(
    model_id: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> AsyncIterator[StreamEvent]:
    adapter, _ = await _resolve_adapter("ai_chat_models", model_id)
    provider = get_provider(adapter, "chat")
    async for event in provider.stream(model_id, messages, **kwargs):
        yield event


async def embed(
    model_id: str,
    texts: list[str],
) -> list[list[float]]:
    adapter, _ = await _resolve_adapter("ai_embedding_models", model_id)
    provider = get_provider(adapter, "embedding")
    return await provider.embed(model_id, texts)


async def rerank(
    model_id: str,
    query: str,
    documents: list[str],
    top_n: int = 5,
) -> list[RerankResult]:
    adapter, _ = await _resolve_adapter("ai_rerank_models", model_id)
    provider = get_provider(adapter, "rerank")
    return await provider.rerank(model_id, query, documents, top_n)
