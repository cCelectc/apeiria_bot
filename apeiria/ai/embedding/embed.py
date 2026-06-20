from __future__ import annotations

from apeiria.ai.model.entry import embed as model_embed


async def embed(model_id: str, texts: list[str]) -> list[list[float]]:
    return await model_embed(model_id, texts)
