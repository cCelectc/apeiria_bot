from __future__ import annotations

from typing import Any

import aiohttp

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult

_MAX_RESULTS = 5


async def _execute(
    *,
    query: str,
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    settings = _ctx.get("settings") if _ctx else None
    if not settings or not settings.searxng_url:
        return ToolResult(success=False, error="Search engine not configured")
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{settings.searxng_url}/search",
                params={"q": query, "format": "json"},
            ) as resp,
        ):
            resp.raise_for_status()
            data = await resp.json()
        results = data.get("results", [])[:_MAX_RESULTS]
        if not results:
            return ToolResult(success=True, content="No search results found.")
        lines = [
            f"{i + 1}. {r.get('title', '')}"
            f" | {r.get('url', '')}"
            f" | {r.get('content', '')[:200]}"
            for i, r in enumerate(results)
        ]
        return ToolResult(success=True, content="\n".join(lines))
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            success=False,
            error=f"Search engine unavailable: {e}",
        )


web_search_tool = Tool(
    name="web_search",
    description="Search the web using the configured search engine.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
        },
        "required": ["query"],
    },
    execute=_execute,
)

register_tool(web_search_tool)
