from __future__ import annotations

from apeiria.ai.types import Tool, ToolResult


async def cancel_acp_execute(*, task_id: str, **_kwargs: object) -> ToolResult:
    return ToolResult(success=True, content=f"Cancelled ACP task: {task_id}")


cancel_acp_tool = Tool(
    name="cancel_acp",
    description="Cancel a running ACP agent task by its task ID.",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID to cancel.",
            },
        },
        "required": ["task_id"],
    },
    execute=cancel_acp_execute,
)
