"""Memory tool handlers — memory.query and memory.update."""

from __future__ import annotations

from typing import Annotated

from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import (
    AIMemoryQueryObservationOutput,
    AIMemoryUpdateObservationOutput,
    AIToolExecutionContext,
    AIToolResult,
)


@ai_tool(
    name="memory.query",
    description="inspect recalled long-term memory",
    read_only=True,
    concurrency_safe=True,
)
async def handle_memory_query(
    query_text: Annotated[  # noqa: ARG001
        str,
        "The lookup query for recalled persistent memory context.",
    ],
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Return recalled memories matching the query."""

    if not context.recalled_memory_contents:
        return AIToolResult(
            summary="- [memory.query] No recalled memories available.",
            output_payload=AIMemoryQueryObservationOutput(memory_ids=()),
        )

    memory_text = "; ".join(
        f"{mid}={content}"
        for mid, content in zip(
            context.recalled_memory_ids[:3],
            context.recalled_memory_contents[:3],
            strict=False,
        )
    )
    return AIToolResult(
        summary=f"- [memory.query] Retrieved relevant memories: {memory_text}",
        output_payload=AIMemoryQueryObservationOutput(
            memory_ids=context.recalled_memory_ids,
        ),
    )


@ai_tool(
    name="memory.update",
    description="revise one recalled memory when it is inaccurate",
    read_only=False,
    concurrency_safe=False,
    risk_level="low",
)
async def handle_memory_update(
    memory_id: Annotated[
        str,
        "One recalled memory_id from memory.query or prior tool "
        "results in the current scene.",
    ],
    updated_content: Annotated[str, "Replacement memory content."],
    salience: Annotated[
        float | None, "Optional revised salience between 0 and 1."
    ] = None,
    confidence: Annotated[
        float | None, "Optional revised confidence between 0 and 1."
    ] = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Update one recalled memory entry."""

    from apeiria.ai.memory.service import (
        AIMemoryUpdateInput as AIMemoryUpdateWriteInput,
    )
    from apeiria.ai.memory.service import ai_memory_service

    if memory_id not in context.recalled_memory_ids:
        return AIToolResult(
            summary=(
                "- [memory.update] failed: memory_id is not available in the "
                "current recalled memory set"
            ),
            output_payload={"ok": False, "message": "memory_id not recalled"},
            status="error",
        )

    existing = await ai_memory_service.get_memory(memory_id=memory_id)
    if existing is None:
        return AIToolResult(
            summary=f"- [memory.update] failed: memory {memory_id} was not found",
            output_payload={"ok": False, "message": "memory not found"},
            status="error",
        )
    if (
        not existing.is_editable
        or existing.is_ignored
        or existing.memory_layer not in {"long_term", "knowledge", "operator"}
    ):
        return AIToolResult(
            summary=(
                f"- [memory.update] failed: memory {memory_id} is not editable "
                "in this layer"
            ),
            output_payload={"ok": False, "message": "memory not editable"},
            status="error",
        )

    row = await ai_memory_service.update_memory_content(
        memory_id=memory_id,
        update_input=AIMemoryUpdateWriteInput(
            content=updated_content,
            salience=salience if salience is not None else 0.8,
            confidence=confidence if confidence is not None else 0.85,
            source_message_id=context.source_message_id,
        ),
    )
    if row is None:
        return AIToolResult(
            summary="- [memory.update] failed: update returned no row",
            output_payload={"ok": False, "message": "memory not found"},
            status="error",
        )

    if row.memory_layer == "knowledge":
        await ai_memory_service.upsert_memory_embedding(
            memory_id=row.memory_id,
            content=row.content,
        )

    return AIToolResult(
        summary=f"- [memory.update] Updated {row.memory_id}: {row.content}",
        output_payload=AIMemoryUpdateObservationOutput(
            memory_id=row.memory_id,
            content=row.content,
            salience=row.salience,
            confidence=row.confidence,
        ),
    )
