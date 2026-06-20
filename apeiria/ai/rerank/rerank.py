from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.entry import rerank as model_rerank

if TYPE_CHECKING:
    from apeiria.ai.types import RerankResult


async def rerank(
    model_id: str,
    query: str,
    documents: list[str],
    top_n: int = 5,
) -> list[RerankResult]:
    return await model_rerank(model_id, query, documents, top_n)
