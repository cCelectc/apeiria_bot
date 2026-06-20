from __future__ import annotations

from typing import Any

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _execute(
    *,
    query: str,
    top_k: int = 5,
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    from apeiria.ai.knowledge.service import retrieve

    results = await retrieve(query, top_k=top_k)
    if not results:
        return ToolResult(success=True, content="No knowledge found.")
    lines = [f"[{score:.2f}] {chunk.content[:300]}" for chunk, score in results]
    return ToolResult(success=True, content="\n---\n".join(lines))


search_knowledge_tool = Tool(
    name="search_knowledge",
    description="Search the knowledge base for relevant information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "top_k": {
                "type": "integer",
                "description": "Max results to return.",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    execute=_execute,
)

register_tool(search_knowledge_tool)
