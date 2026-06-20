from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx

from apeiria.ai.model.registry import register_provider
from apeiria.ai.types import RerankResult

_DEFAULT_TIMEOUT = 20


@register_provider("generic_rerank")
class GenericRerankProvider:
    capabilities: ClassVar[set[str]] = {"rerank"}

    async def rerank(
        self,
        model_id: str,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        config = await self._get_source_config(model_id)
        api_base = config.get("api_base", "")
        api_key = config.get("api_key", "")
        model_identifier = config.get("model_identifier", model_id)

        if not api_base:
            msg = "Rerank provider requires api_base"
            raise ValueError(msg)

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_identifier,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        async with httpx.AsyncClient(
            base_url=api_base.rstrip("/"),
            headers=headers,
            timeout=float(_DEFAULT_TIMEOUT),
        ) as client:
            response = await client.post("/rerank", json=payload)
            response.raise_for_status()
            raw = response.json()

        results: list[RerankResult] = []
        for row in raw.get("results", []):
            if not isinstance(row, dict):
                continue
            index = row.get("index")
            score = row.get("relevance_score", row.get("score"))
            if not isinstance(index, int) or not isinstance(score, (int, float)):
                continue
            text = documents[index] if 0 <= index < len(documents) else None
            results.append(RerankResult(index=index, score=float(score), text=text))
        return results

    async def _get_source_config(self, model_id: str) -> dict[str, Any]:
        from sqlalchemy import text as sa_text

        from apeiria.db.engine import get_session

        async with get_session() as session:
            row = (
                await session.execute(
                    sa_text(
                        "SELECT source_id, model_identifier "
                        "FROM ai_rerank_models WHERE model_id = :mid"
                    ),
                    {"mid": model_id},
                )
            ).first()
            if not row:
                return {"model_identifier": model_id}
            source_id, model_identifier = row

            source = (
                await session.execute(
                    sa_text(
                        "SELECT api_base, api_key_env "
                        "FROM ai_sources WHERE source_id = :sid"
                    ),
                    {"sid": source_id},
                )
            ).first()
            if not source:
                return {"model_identifier": model_identifier}

            api_key = os.environ.get(source[1], "") if source[1] else ""
            return {
                "api_base": source[0],
                "api_key": api_key,
                "model_identifier": model_identifier,
            }
