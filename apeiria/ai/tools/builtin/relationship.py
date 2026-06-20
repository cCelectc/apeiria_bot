from __future__ import annotations

from typing import Any

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _execute(
    *,
    user_id: str,
    delta: float,
    reason: str = "",
    _ctx: dict[str, Any] | None = None,
) -> ToolResult:
    from apeiria.ai.relationship.service import adjust

    session_id = _ctx.get("session_id", "") if _ctx else ""
    score = await adjust(user_id, session_id, delta)
    return ToolResult(
        success=True,
        content=(
            f"Relationship adjusted by {delta:+.1f}."
            f" Current: {score.score:.0f}/100."
            f" Reason: {reason}"
        ),
    )


adjust_relationship_tool = Tool(
    name="adjust_relationship",
    description=(
        "Adjust the relationship score with a user. Positive delta"
        " increases closeness, negative decreases it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The target user ID.",
            },
            "delta": {
                "type": "number",
                "description": ("Score adjustment (-10.0 to +10.0 recommended)."),
            },
            "reason": {
                "type": "string",
                "description": "Reason for the adjustment.",
                "default": "",
            },
        },
        "required": ["user_id", "delta"],
    },
    execute=_execute,
)

register_tool(adjust_relationship_tool)
