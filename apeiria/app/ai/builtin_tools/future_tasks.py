"""App-owned future-task AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import (
    AIToolExecutionContext,
    AIToolLevel,
    AIToolResult,
)
from apeiria.app.ai.builtin_tools.common import (
    bounded_int,
    bounded_text,
    clean_required_text,
    context_payload,
    denied_result,
    error_result,
    parse_iso_datetime,
)

if TYPE_CHECKING:
    from apeiria.app.ai.future_tasks import AIFutureTasksEntry
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.conversation.models import ChatSessionIdentity

_MAX_FUTURE_TASK_RESULTS = 10


@ai_tool(
    name="future_task.create",
    description="Schedule one follow-up task for the current chat.",
    required_level=AIToolLevel.WRITE,
)
async def create_future_task(
    description: Annotated[str, "Follow-up content."],
    trigger_at: Annotated[str, "Absolute ISO-8601 datetime with timezone offset."],
    title: Annotated[str | None, "Optional short title."] = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Create one durable future task through the application entry."""

    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput

    identity = await _load_chat_identity(context)
    if identity is None:
        return error_result("future_task.create", "session identity is missing")
    parsed_trigger = parse_iso_datetime(trigger_at)
    if parsed_trigger is None:
        return error_result(
            "future_task.create",
            "trigger_at must be an absolute ISO datetime with timezone",
        )

    cleaned_description = bounded_text(
        clean_required_text(description, field="description")
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
        return denied_result("future_task.create", str(exc))

    task = result.task
    ok = task.status == "pending"
    return AIToolResult(
        summary=(
            f"- [future_task.create] {'scheduled' if ok else 'failed'} {task.task_id}"
        ),
        output_payload={
            "ok": ok,
            "task": _future_task_item(task),
            "context": context_payload(context),
        },
        status="success" if ok else "error",
    )


@ai_tool(
    name="future_task.list",
    description="List scheduled follow-up tasks for the current chat.",
    required_level=AIToolLevel.READ,
)
async def list_future_tasks(
    limit: Annotated[int | None, "Maximum tasks, 1-10."] = 5,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """List current-chat future tasks through the application entry."""

    try:
        tasks = await _resolve_future_tasks_entry().list_tasks(
            limit=bounded_int(
                limit,
                default=5,
                minimum=1,
                maximum=_MAX_FUTURE_TASK_RESULTS,
            ),
            session_id=context.session_id,
        )
    except PermissionError as exc:
        return denied_result("future_task.list", str(exc))

    return AIToolResult(
        summary=f"- [future_task.list] listed {len(tasks)} tasks",
        output_payload={
            "tasks": [_future_task_item(task) for task in tasks],
            "context": context_payload(context),
        },
    )


@ai_tool(
    name="future_task.cancel",
    description="Cancel one scheduled follow-up task for the current chat.",
    required_level=AIToolLevel.WRITE,
)
async def cancel_future_task(
    task_id: Annotated[str, "Scheduled task id to cancel."],
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Cancel one current-chat future task through the application entry."""

    task_id = clean_required_text(task_id, field="task_id")
    entry = _resolve_future_tasks_entry()
    existing = await entry.get_task(task_id=task_id)
    if existing is None:
        return error_result("future_task.cancel", f"task {task_id} was not found")
    if existing.session_id != context.session_id:
        return error_result(
            "future_task.cancel",
            "task does not belong to the current session",
        )
    try:
        cancelled = await entry.cancel_task(
            task_id=task_id,
            actor_username=context.actor_id,
        )
    except PermissionError as exc:
        return denied_result("future_task.cancel", str(exc))
    if cancelled is None:
        return error_result("future_task.cancel", f"task {task_id} was not found")

    return AIToolResult(
        summary=f"- [future_task.cancel] cancelled {task_id}",
        output_payload={
            "ok": True,
            "task": _future_task_item(cancelled),
            "context": context_payload(context),
        },
    )


async def _load_chat_identity(
    context: AIToolExecutionContext,
) -> "ChatSessionIdentity | None":
    from apeiria.conversation.service import chat_session_service

    return await chat_session_service.get_session_identity(
        session_id=context.session_id,
    )


def _resolve_future_tasks_entry() -> "AIFutureTasksEntry":
    from apeiria.app.ai import ai_application

    return ai_application.future_tasks


def _future_task_item(task: "AIFutureTaskDefinition") -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "title": task.title,
        "description": bounded_text(task.description),
        "trigger_at": task.trigger_at.isoformat(),
        "status": task.status,
    }
