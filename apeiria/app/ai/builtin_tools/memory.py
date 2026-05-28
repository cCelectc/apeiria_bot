"""App-owned memory AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from apeiria.ai.memory.contracts import AIMemoryCreateInput, AIMemoryUpdateInput
from apeiria.ai.memory.models import AIMemoryQuery
from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import AIToolExecutionContext, AIToolLevel, AIToolResult
from apeiria.app.ai.builtin_tools.common import (
    bounded_float,
    bounded_int,
    bounded_text,
    clean_required_text,
    context_payload,
    denied_result,
    error_result,
    optional_choice,
    short_text,
)
from apeiria.app.ai.wiring import ai_wiring

if TYPE_CHECKING:
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryKind,
        AIMemoryLayer,
    )

_MAX_MEMORY_RESULTS = 10
_MEMORY_KINDS: set[str] = {"fact", "preference", "relationship", "note", "impression"}
_MEMORY_LAYERS: set[str] = {"summary", "long_term", "knowledge", "operator"}


@ai_tool(
    name="memory.search",
    description="Search durable memory when compact context is not enough.",
    required_level=AIToolLevel.READ,
)
async def search_memory(
    query_text: Annotated[str, "Search text for durable memory lookup."],
    limit: Annotated[int | None, "Maximum results, 1-10."] = 5,
    memory_layer: Annotated[str | None, "Optional memory layer."] = None,
    memory_kind: Annotated[str | None, "Optional memory kind."] = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Search actor-accessible memory through the memory service."""

    query_text = clean_required_text(query_text, field="query_text")
    anchor_type, anchor_id = _memory_anchor_from_context(context)
    query = AIMemoryQuery(
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        query_text=query_text,
        limit=bounded_int(limit, default=5, minimum=1, maximum=_MAX_MEMORY_RESULTS),
        memory_layer=cast(
            "AIMemoryLayer | None",
            optional_choice(memory_layer, _MEMORY_LAYERS),
        ),
        memory_kind=cast(
            "AIMemoryKind | None",
            optional_choice(memory_kind, _MEMORY_KINDS),
        ),
    )
    try:
        memories = await ai_wiring.memory_service.retrieve_memories(query)
    except PermissionError as exc:
        return denied_result("memory.search", str(exc))

    items = [_memory_item(memory) for memory in memories[: query.limit]]
    return AIToolResult(
        summary=(
            f"- [memory.search] found {len(items)} memories for "
            f"{anchor_type}:{anchor_id}"
        ),
        output_payload={
            "query_text": query.query_text,
            "results": items,
            "context": context_payload(context),
        },
    )


@ai_tool(
    name="memory.write",
    description="Create or correct durable memory from a clear fact.",
    required_level=AIToolLevel.WRITE,
)
async def write_memory(  # noqa: PLR0913
    content: Annotated[str, "Durable fact, preference, correction, or note."],
    memory_kind: Annotated[str | None, "Memory kind; defaults to note."] = None,
    memory_id: Annotated[str | None, "Optional existing memory id to correct."] = None,
    salience: Annotated[float | None, "Importance from 0 to 1."] = 0.7,
    confidence: Annotated[float | None, "Confidence from 0 to 1."] = 0.8,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Create or correct one durable long-term memory."""

    content = bounded_text(clean_required_text(content, field="content"))
    normalized_kind = cast(
        "AIMemoryKind",
        optional_choice(memory_kind, _MEMORY_KINDS, default="note"),
    )
    normalized_salience = bounded_float(salience, default=0.7)
    normalized_confidence = bounded_float(confidence, default=0.8)
    if memory_id is not None and memory_id.strip():
        return await _update_memory(
            memory_id=memory_id.strip(),
            content=content,
            salience=normalized_salience,
            confidence=normalized_confidence,
            context=context,
        )

    anchor_type, anchor_id = _memory_anchor_from_context(context)
    create_input = AIMemoryCreateInput(
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        memory_layer="long_term",
        memory_kind=normalized_kind,
        content=content,
        is_editable=True,
        source_message_id=context.source_message_id,
        salience=normalized_salience,
        confidence=normalized_confidence,
    )
    try:
        memory = await ai_wiring.memory_service.create_memory(create_input)
    except PermissionError as exc:
        return denied_result("memory.write", str(exc))

    return AIToolResult(
        summary=(
            f"- [memory.write] stored {memory.memory_id}: {short_text(memory.content)}"
        ),
        output_payload=_memory_item(memory),
    )


async def _update_memory(
    *,
    memory_id: str,
    content: str,
    salience: float,
    confidence: float,
    context: AIToolExecutionContext,
) -> AIToolResult:
    existing = await ai_wiring.memory_service.get_memory(memory_id=memory_id)
    if existing is None:
        return error_result("memory.write", f"memory {memory_id} was not found")
    if not existing.is_editable or existing.lifecycle_state != "active":
        return error_result("memory.write", f"memory {memory_id} is not editable")
    try:
        updated = await ai_wiring.memory_service.update_memory_content(
            memory_id=memory_id,
            update_input=AIMemoryUpdateInput(
                content=content,
                salience=salience,
                confidence=confidence,
                source_message_id=context.source_message_id,
            ),
        )
    except PermissionError as exc:
        return denied_result("memory.write", str(exc))
    if updated is None:
        return error_result("memory.write", f"memory {memory_id} was not found")
    return AIToolResult(
        summary=(
            f"- [memory.write] updated {updated.memory_id}: "
            f"{short_text(updated.content)}"
        ),
        output_payload=_memory_item(updated),
    )


def _memory_anchor_from_context(
    context: AIToolExecutionContext,
) -> tuple["AIMemoryAnchorType", str]:
    actor_id = (context.actor_id or "").strip()
    if actor_id:
        return "user", actor_id
    return "scene", context.session_id


def _memory_item(memory: "AIMemoryDefinition") -> dict[str, object]:
    return {
        "memory_id": memory.memory_id,
        "anchor_type": memory.anchor_type,
        "anchor_id": memory.anchor_id,
        "memory_layer": memory.memory_layer,
        "memory_kind": memory.memory_kind,
        "lifecycle_state": memory.lifecycle_state,
        "use_mode": memory.default_use_mode,
        "content": bounded_text(memory.content),
        "salience": memory.salience,
        "confidence": memory.confidence,
    }
