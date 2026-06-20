from __future__ import annotations

from apeiria.ai.tools.registry import register_tool
from apeiria.ai.types import Tool, ToolResult


async def _execute(*, name: str, **_kwargs: object) -> ToolResult:
    from apeiria.ai.skills.catalog import get_skill_body

    body = get_skill_body(name)
    if body is None:
        return ToolResult(success=False, error=f"Unknown skill: {name}")
    return ToolResult(success=True, content=body)


load_skill_tool = Tool(
    name="load_skill",
    description="Load a skill by name to gain specialised instructions.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The skill name to load.",
            },
        },
        "required": ["name"],
    },
    execute=_execute,
)

register_tool(load_skill_tool)
