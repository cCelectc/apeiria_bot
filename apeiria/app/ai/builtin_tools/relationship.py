"""App-owned relationship AI tools."""

from __future__ import annotations

from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import (
    AIRelationshipInspectObservationOutput,
    AIToolExecutionContext,
    AIToolLevel,
    AIToolResult,
)


@ai_tool(
    name="relationship.inspect",
    description="inspect current affinity and mood projection",
    required_level=AIToolLevel.READ,
)
async def inspect_relationship(
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
