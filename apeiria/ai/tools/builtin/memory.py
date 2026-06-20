from __future__ import annotations

from typing import Any

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _search_execute(
    *,
    query: str,
    top_k: int = 10,
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    if not _ctx:
        return ToolResult(success=False, error="No session context")
    from apeiria.ai.memory.service import search

    settings = _ctx.get("settings")
    if not settings:
        return ToolResult(success=False, error="No settings in context")
    user_id = _ctx.get("user_id", "")
    session_id = _ctx.get("session_id", "")
    facts = await search(user_id, session_id, query, settings=settings, top_k=top_k)
    if not facts:
        return ToolResult(success=True, content="No memories found.")
    lines = [f"- [{f.importance:.2f}] {f.content}" for f in facts]
    return ToolResult(success=True, content="\n".join(lines))


async def _remember_execute(
    *,
    user_id: str,
    content: str,
    importance: float = 0.5,
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    from apeiria.ai.memory.service import remember

    session_id = _ctx.get("session_id", "") if _ctx else ""
    fact = await remember(user_id, session_id, content, importance)
    return ToolResult(success=True, content=f"Remembered: {fact.content}")


search_memory_tool = Tool(
    name="search_memory",
    description="Search long-term memory for facts about a user or topic.",
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
                "default": 10,
            },
        },
        "required": ["query"],
    },
    execute=_search_execute,
)

remember_tool = Tool(
    name="remember",
    description=("Store a fact about a user into long-term memory for future recall."),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user to associate the memory with.",
            },
            "content": {
                "type": "string",
                "description": "The fact or information to remember.",
            },
            "importance": {
                "type": "number",
                "description": "Importance score from 0.0 to 1.0.",
                "default": 0.5,
            },
        },
        "required": ["user_id", "content"],
    },
    execute=_remember_execute,
)

register_tool(search_memory_tool)
register_tool(remember_tool)
