"""Compatibility helpers for exposing approved legacy commands as AI tools."""

from __future__ import annotations

from typing import Any

from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolLevel,
    AIToolReadiness,
)


def legacy_command_tool_definition(
    *,
    command_name: str,
    description: str,
    approved: bool,
    executor: Any,
) -> AIToolDefinition:
    """Return an admin-level compatibility tool for one legacy command."""

    safe_name = command_name.replace(".", "_").replace("-", "_")
    readiness = (
        AIToolReadiness.available()
        if approved
        else AIToolReadiness.not_ready(
            "approval_missing",
            "legacy command approval is missing",
        )
    )
    return AIToolDefinition(
        name=f"legacy_command.{safe_name}",
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "arguments": {
                    "type": "object",
                    "description": "Legacy command arguments.",
                }
            },
            "additionalProperties": False,
        },
        required_level=AIToolLevel.ADMIN,
        executor=executor if approved else None,
        readiness=readiness,
        origin="legacy",
        manageable=True,
        tags=("legacy_command",),
    )


__all__ = ["legacy_command_tool_definition"]
