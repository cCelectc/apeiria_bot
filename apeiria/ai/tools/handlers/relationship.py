"""Relationship tool handler — relationship.inspect."""

from __future__ import annotations

from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import (
    AIRelationshipInspectObservationOutput,
    AIToolExecutionContext,
    AIToolResult,
)


@ai_tool(
    name="relationship.inspect",
    description="inspect current affinity and mood projection",
    read_only=True,
    concurrency_safe=True,
)
async def handle_relationship_inspect(
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Return the relationship context for the current session."""

    if not context.relationship_context:
        return AIToolResult(
            summary="- [relationship.inspect] No relationship data available.",
            output_payload=AIRelationshipInspectObservationOutput(
                relationship_context="",
            ),
        )

    return AIToolResult(
        summary=f"- [relationship.inspect] {context.relationship_context}",
        output_payload=AIRelationshipInspectObservationOutput(
            relationship_context=context.relationship_context,
        ),
    )
