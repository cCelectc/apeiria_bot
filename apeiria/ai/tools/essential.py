"""Essential builtin AI tool facades over existing capability services."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.knowledge.service import knowledge_retrieval_service
from apeiria.ai.knowledge.settings import knowledge_settings_store
from apeiria.ai.memory.contracts import AIMemoryCreateInput, AIMemoryUpdateInput
from apeiria.ai.memory.models import AIMemoryQuery
from apeiria.ai.memory.service import ai_memory_service
from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolExecutionContext,
    AIToolLevel,
    AIToolReadiness,
    AIToolResult,
)

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
    )
    from apeiria.ai.memory.models import (
        AIMemoryAnchorType,
        AIMemoryDefinition,
        AIMemoryKind,
        AIMemoryLayer,
    )
    from apeiria.app.ai.future_tasks import AIFutureTasksEntry
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.conversation.models import ChatSessionIdentity

_MAX_MEMORY_RESULTS = 10
_MAX_KNOWLEDGE_RESULTS = 5
_MAX_FUTURE_TASK_RESULTS = 10
_MAX_EXCERPT_CHARS = 320
_MAX_CONTENT_CHARS = 500
_MEMORY_KINDS: set[str] = {"fact", "preference", "relationship", "note", "impression"}
_MEMORY_LAYERS: set[str] = {"summary", "long_term", "knowledge", "operator"}


def build_essential_builtin_tools() -> tuple[AIToolDefinition, ...]:
    """Build the first essential builtin AI tool catalog."""

    return (
        AIToolDefinition(
            name="memory.search",
            description="Search durable memory when compact context is not enough.",
            input_schema=_memory_search_schema(),
            required_level=AIToolLevel.READ,
            executor=search_memory,
            origin="builtin",
            tags=("essential", "memory", "read"),
        ),
        AIToolDefinition(
            name="memory.write",
            description="Create or correct durable memory from a clear fact.",
            input_schema=_memory_write_schema(),
            required_level=AIToolLevel.WRITE,
            executor=write_memory,
            origin="builtin",
            tags=("essential", "memory", "write"),
        ),
        AIToolDefinition(
            name="knowledge.search",
            description="Search configured knowledge sources for grounded detail.",
            input_schema=_knowledge_search_schema(),
            required_level=AIToolLevel.READ,
            executor=search_knowledge,
            readiness=_knowledge_readiness(),
            origin="builtin",
            tags=("essential", "knowledge", "read"),
        ),
        AIToolDefinition(
            name="future_task.create",
            description="Schedule one follow-up task for the current chat.",
            input_schema=_future_task_create_schema(),
            required_level=AIToolLevel.WRITE,
            executor=create_future_task,
            origin="builtin",
            tags=("essential", "future_task", "write"),
        ),
        AIToolDefinition(
            name="future_task.list",
            description="List scheduled follow-up tasks for the current chat.",
            input_schema=_future_task_list_schema(),
            required_level=AIToolLevel.READ,
            executor=list_future_tasks,
            origin="builtin",
            tags=("essential", "future_task", "read"),
        ),
        AIToolDefinition(
            name="future_task.cancel",
            description="Cancel one scheduled follow-up task for the current chat.",
            input_schema=_future_task_cancel_schema(),
            required_level=AIToolLevel.WRITE,
            executor=cancel_future_task,
            origin="builtin",
            tags=("essential", "future_task", "write"),
        ),
    )


async def search_memory(
    query_text: str,
    limit: int | None = None,
    memory_layer: str | None = None,
    memory_kind: str | None = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Search actor-accessible memory through the memory service."""

    query_text = _clean_required_text(query_text, field="query_text")
    anchor_type, anchor_id = _memory_anchor_from_context(context)
    query = AIMemoryQuery(
        anchor_type=anchor_type,
        anchor_id=anchor_id,
        query_text=query_text,
        limit=_bounded_int(limit, default=5, minimum=1, maximum=_MAX_MEMORY_RESULTS),
        memory_layer=cast(
            "AIMemoryLayer | None",
            _optional_choice(memory_layer, _MEMORY_LAYERS),
        ),
        memory_kind=cast(
            "AIMemoryKind | None",
            _optional_choice(memory_kind, _MEMORY_KINDS),
        ),
    )
    try:
        memories = await ai_memory_service.retrieve_memories(query)
    except PermissionError as exc:
        return _denied("memory.search", str(exc))

    items = [_memory_item(memory) for memory in memories[: query.limit]]
    return AIToolResult(
        summary=(
            f"- [memory.search] found {len(items)} memories for "
            f"{anchor_type}:{anchor_id}"
        ),
        output_payload={
            "query_text": query.query_text,
            "results": items,
            "context": _context_payload(context),
        },
    )


async def write_memory(  # noqa: PLR0913
    content: str,
    memory_kind: str | None = None,
    memory_id: str | None = None,
    salience: float | None = None,
    confidence: float | None = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Create or correct one durable long-term memory."""

    content = _bounded_text(_clean_required_text(content, field="content"))
    normalized_kind = cast(
        "AIMemoryKind",
        _optional_choice(memory_kind, _MEMORY_KINDS, default="note"),
    )
    normalized_salience = _bounded_float(salience, default=0.7)
    normalized_confidence = _bounded_float(confidence, default=0.8)
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
        memory = await ai_memory_service.create_memory(create_input)
    except PermissionError as exc:
        return _denied("memory.write", str(exc))

    return AIToolResult(
        summary=f"- [memory.write] stored {memory.memory_id}: {_short(memory.content)}",
        output_payload=_memory_item(memory),
    )


async def search_knowledge(
    query_text: str,
    limit: int | None = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Search configured knowledge retrieval through the knowledge service."""

    del context
    query_text = _clean_required_text(query_text, field="query_text")
    bounded_limit = _bounded_int(
        limit,
        default=3,
        minimum=1,
        maximum=_MAX_KNOWLEDGE_RESULTS,
    )
    try:
        result = await knowledge_retrieval_service.retrieve(
            query_text=query_text,
            limit=bounded_limit,
            mutate_embeddings=False,
        )
    except PermissionError as exc:
        return _denied("knowledge.search", str(exc))

    return AIToolResult(
        summary=f"- [knowledge.search] found {len(result.items)} chunks",
        output_payload={
            "items": [_knowledge_item(item) for item in result.items[:bounded_limit]],
            "diagnostics": _knowledge_diagnostics(result.diagnostics),
        },
    )


async def create_future_task(
    description: str,
    trigger_at: str,
    title: str | None = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Create one durable future task through the application entry."""

    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput

    identity = await _load_chat_identity(context)
    if identity is None:
        return _error("future_task.create", "session identity is missing")
    parsed_trigger = _parse_iso_datetime(trigger_at)
    if parsed_trigger is None:
        return _error(
            "future_task.create",
            "trigger_at must be an absolute ISO datetime with timezone",
        )

    cleaned_description = _bounded_text(
        _clean_required_text(description, field="description")
    )
    create_input = AIFutureTaskCreateInput(
        session_id=identity.session_id,
        platform=identity.platform,
        scene_type=identity.scene_type,
        scene_id=identity.scene_id,
        user_id=identity.subject_id,
        title=(title or cleaned_description[:32]).strip(),
        description=cleaned_description,
        trigger_at=parsed_trigger,
        source_message_id=context.source_message_id,
    )
    try:
        result = await _resolve_future_tasks_entry().create_task(create_input)
    except PermissionError as exc:
        return _denied("future_task.create", str(exc))

    task = result.task
    ok = task.status == "pending"
    return AIToolResult(
        summary=(
            f"- [future_task.create] {'scheduled' if ok else 'failed'} {task.task_id}"
        ),
        output_payload={
            "ok": ok,
            "task": _future_task_item(task),
            "context": _context_payload(context),
        },
        status="success" if ok else "error",
    )


async def list_future_tasks(
    limit: int | None = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """List current-chat future tasks through the application entry."""

    try:
        tasks = await _resolve_future_tasks_entry().list_tasks(
            limit=_bounded_int(
                limit,
                default=5,
                minimum=1,
                maximum=_MAX_FUTURE_TASK_RESULTS,
            ),
            session_id=context.session_id,
        )
    except PermissionError as exc:
        return _denied("future_task.list", str(exc))

    return AIToolResult(
        summary=f"- [future_task.list] listed {len(tasks)} tasks",
        output_payload={
            "tasks": [_future_task_item(task) for task in tasks],
            "context": _context_payload(context),
        },
    )


async def cancel_future_task(
    task_id: str,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Cancel one current-chat future task through the application entry."""

    task_id = _clean_required_text(task_id, field="task_id")
    entry = _resolve_future_tasks_entry()
    existing = await entry.get_task(task_id=task_id)
    if existing is None:
        return _error("future_task.cancel", f"task {task_id} was not found")
    if existing.session_id != context.session_id:
        return _error(
            "future_task.cancel",
            "task does not belong to the current session",
        )
    try:
        cancelled = await entry.cancel_task(
            task_id=task_id,
            actor_username=context.actor_id,
        )
    except PermissionError as exc:
        return _denied("future_task.cancel", str(exc))
    if cancelled is None:
        return _error("future_task.cancel", f"task {task_id} was not found")

    return AIToolResult(
        summary=f"- [future_task.cancel] cancelled {task_id}",
        output_payload={
            "ok": True,
            "task": _future_task_item(cancelled),
            "context": _context_payload(context),
        },
    )


async def _update_memory(
    *,
    memory_id: str,
    content: str,
    salience: float,
    confidence: float,
    context: AIToolExecutionContext,
) -> AIToolResult:
    existing = await ai_memory_service.get_memory(memory_id=memory_id)
    if existing is None:
        return _error("memory.write", f"memory {memory_id} was not found")
    if not existing.is_editable or existing.is_ignored:
        return _error("memory.write", f"memory {memory_id} is not editable")
    try:
        updated = await ai_memory_service.update_memory_content(
            memory_id=memory_id,
            update_input=AIMemoryUpdateInput(
                content=content,
                salience=salience,
                confidence=confidence,
                source_message_id=context.source_message_id,
            ),
        )
    except PermissionError as exc:
        return _denied("memory.write", str(exc))
    if updated is None:
        return _error("memory.write", f"memory {memory_id} was not found")
    return AIToolResult(
        summary=(
            f"- [memory.write] updated {updated.memory_id}: {_short(updated.content)}"
        ),
        output_payload=_memory_item(updated),
    )


def _knowledge_readiness() -> AIToolReadiness:
    if knowledge_settings_store.get().rag_enabled:
        return AIToolReadiness.available()
    return AIToolReadiness.not_ready(
        "runtime_missing_capability",
        "knowledge retrieval is disabled",
    )


def _memory_anchor_from_context(
    context: AIToolExecutionContext,
) -> tuple["AIMemoryAnchorType", str]:
    actor_id = (context.actor_id or "").strip()
    if actor_id:
        return "user", actor_id
    return "scene", context.session_id


async def _load_chat_identity(
    context: AIToolExecutionContext,
) -> "ChatSessionIdentity | None":
    from apeiria.conversation import service as conversation_service

    return await conversation_service.chat_session_service.get_session_identity(
        session_id=context.session_id,
    )


def _resolve_future_tasks_entry() -> "AIFutureTasksEntry":
    from apeiria.app.ai import ai_application

    return cast("AIFutureTasksEntry", ai_application.future_tasks)


def _memory_item(memory: "AIMemoryDefinition") -> dict[str, object]:
    return {
        "memory_id": memory.memory_id,
        "anchor_type": memory.anchor_type,
        "anchor_id": memory.anchor_id,
        "memory_layer": memory.memory_layer,
        "memory_kind": memory.memory_kind,
        "content": _bounded_text(memory.content),
        "salience": memory.salience,
        "confidence": memory.confidence,
    }


def _knowledge_item(item: "KnowledgeRetrievalItem") -> dict[str, object]:
    return {
        "label": item.label,
        "document_id": item.document_id,
        "chunk_id": item.chunk_id,
        "title": item.title,
        "source_file_name": item.source_file_name,
        "rank": item.rank,
        "score": item.score,
        "excerpt": _bounded_text(item.excerpt, max_chars=_MAX_EXCERPT_CHARS),
    }


def _knowledge_diagnostics(
    diagnostics: "KnowledgeRetrievalDiagnostics",
) -> dict[str, object]:
    return {
        "candidate_count": diagnostics.candidate_count,
        "selected_count": diagnostics.selected_count,
        "missing_embedding_count": diagnostics.missing_embedding_count,
        "stale_embedding_count": diagnostics.stale_embedding_count,
        "rerank_status": diagnostics.rerank_status,
        "degradation_reason": diagnostics.degradation_reason,
    }


def _future_task_item(task: "AIFutureTaskDefinition") -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "title": task.title,
        "description": _bounded_text(task.description),
        "trigger_at": task.trigger_at.isoformat(),
        "status": task.status,
    }


def _context_payload(context: AIToolExecutionContext) -> dict[str, object | None]:
    return {
        "session_id": context.session_id,
        "source_message_id": context.source_message_id,
        "actor_id": context.actor_id,
        "chat_scope_type": context.chat_scope_type,
        "chat_scope_id": context.chat_scope_id,
        "reply_audience": context.reply_audience,
    }


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _clean_required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        msg = f"{field} is required"
        raise ValueError(msg)
    return value.strip()


def _bounded_text(text: str, *, max_chars: int = _MAX_CONTENT_CHARS) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3].rstrip()}..."


def _short(text: str) -> str:
    return _bounded_text(text, max_chars=120)


def _bounded_int(
    value: int | None,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _bounded_float(value: float | None, *, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(parsed, 1.0))


def _optional_choice(
    value: str | None,
    choices: set[str],
    *,
    default: str | None = None,
) -> str | None:
    if value is None:
        return default
    normalized = value.strip()
    if normalized in choices:
        return normalized
    return default


def _error(tool_name: str, message: str) -> AIToolResult:
    return AIToolResult(
        summary=f"- [{tool_name}] failed: {message}",
        output_payload={"ok": False, "error": message},
        status="error",
    )


def _denied(tool_name: str, message: str) -> AIToolResult:
    return AIToolResult(
        summary=f"- [{tool_name}] denied: {message}",
        output_payload={"ok": False, "error": message},
        status="denied",
    )


def _memory_search_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "query_text": _string_schema("Search text for durable memory lookup."),
            "limit": _integer_schema("Maximum results, 1-10.", default=5),
            "memory_layer": _string_schema("Optional memory layer."),
            "memory_kind": _string_schema("Optional memory kind."),
        },
        required=("query_text",),
    )


def _memory_write_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "content": _string_schema("Durable fact, preference, correction, or note."),
            "memory_kind": _string_schema("Memory kind; defaults to note."),
            "memory_id": _string_schema("Optional existing memory id to correct."),
            "salience": _number_schema("Importance from 0 to 1.", default=0.7),
            "confidence": _number_schema("Confidence from 0 to 1.", default=0.8),
        },
        required=("content",),
    )


def _knowledge_search_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "query_text": _string_schema("Search text for configured knowledge."),
            "limit": _integer_schema("Maximum results, 1-5.", default=3),
        },
        required=("query_text",),
    )


def _future_task_create_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "description": _string_schema("Follow-up content."),
            "trigger_at": _string_schema(
                "Absolute ISO-8601 datetime with timezone offset."
            ),
            "title": _string_schema("Optional short title."),
        },
        required=("description", "trigger_at"),
    )


def _future_task_list_schema() -> dict[str, Any]:
    return _object_schema(
        {"limit": _integer_schema("Maximum tasks, 1-10.", default=5)},
    )


def _future_task_cancel_schema() -> dict[str, Any]:
    return _object_schema(
        {"task_id": _string_schema("Scheduled task id to cancel.")},
        required=("task_id",),
    )


def _object_schema(
    properties: dict[str, dict[str, Any]],
    *,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _string_schema(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _integer_schema(description: str, *, default: int) -> dict[str, Any]:
    return {"type": "integer", "description": description, "default": default}


def _number_schema(description: str, *, default: float) -> dict[str, Any]:
    return {"type": "number", "description": description, "default": default}


__all__ = [
    "build_essential_builtin_tools",
    "cancel_future_task",
    "create_future_task",
    "list_future_tasks",
    "search_knowledge",
    "search_memory",
    "write_memory",
]
