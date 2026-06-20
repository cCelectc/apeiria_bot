from __future__ import annotations

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _execute(**_kwargs: object) -> ToolResult:
    return ToolResult(success=True, content="skip")


skip_tool = Tool(
    name="skip_if_not_worth_it",
    description=(
        "Call this tool if the conversation does not warrant a response"
        " from you. Use when messages are not directed at you, are"
        " trivial, or when you have nothing meaningful to add."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
    execute=_execute,
)

register_tool(skip_tool)
