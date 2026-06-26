from __future__ import annotations

import json
from typing import Any

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _execute(
    *,
    query: str,
    limit: int = 20,
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    session_id = _ctx.get("session_id", "") if _ctx else ""
    if not session_id:
        return ToolResult(success=False, error="No session context")

    from apeiria.conversation.service import search_messages_by_keyword

    messages = await search_messages_by_keyword(session_id, query, limit=limit)
    if not messages:
        return ToolResult(success=True, content="No matching messages found.")
    lines: list[str] = []
    for m in reversed(messages):
        prefix = m.user_id or m.role
        content = m.content
        if m.meta_json:
            try:
                meta = json.loads(m.meta_json)
                if isinstance(meta, dict):
                    for key in meta:
                        if key.startswith("Pic:"):
                            content = content.replace(f"[{key}]", "[\u56fe\u7247]")
                        elif key.startswith("Emoji:"):
                            content = content.replace(f"[{key}]", "[\u8868\u60c5]")
            except (json.JSONDecodeError, TypeError):
                pass
        lines.append(f"[{prefix}] {content}")
    return ToolResult(success=True, content="\n".join(lines))


recall_history_tool = Tool(
    name="recall_history",
    description=(
        "Search the current session's message history for messages"
        " matching a keyword query."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword to search in messages.",
            },
            "limit": {
                "type": "integer",
                "description": "Max messages to return.",
                "default": 20,
            },
        },
        "required": ["query"],
    },
    execute=_execute,
)

register_tool(recall_history_tool)
