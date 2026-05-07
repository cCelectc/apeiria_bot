"""Future task tool handler — future_task.manage."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, cast

from apeiria.ai.tools.decorators import ai_tool
from apeiria.ai.tools.models import AIToolExecutionContext, AIToolResult

if TYPE_CHECKING:
    from apeiria.app.ai.future_tasks import AIFutureTasksEntry
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.conversation.models import ChatSessionIdentity

_FutureTaskAction = Literal["create", "cancel", "list"]


@ai_tool(
    name="future_task.manage",
    description="create, cancel, or inspect scheduled reminder tasks",
    read_only=False,
    concurrency_safe=False,
    risk_level="low",
)
async def handle_future_task(  # noqa: PLR0913
    action: Annotated[
        Literal["create", "cancel", "list"],
        "create schedules a reminder, cancel removes one by task_id, "
        "list shows existing tasks for the current conversation.",
    ],
    title: Annotated[str | None, "Short reminder title for create."] = None,
    description: Annotated[str | None, "Reminder content for create."] = None,
    trigger_at: Annotated[
        str | None,
        "Absolute ISO-8601 datetime with timezone offset for create.",
    ] = None,
    task_id: Annotated[str | None, "Existing task_id for cancel."] = None,
    limit: Annotated[int | None, "Optional max items for list, default 5."] = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Manage scheduled reminder tasks."""

    from apeiria.conversation.service import chat_session_service

    identity = await chat_session_service.get_session_identity(
        session_id=context.session_id,
    )
    if identity is None:
        return _error_result(action, "session identity is missing")

    if action == "create":
        return await _create_action(
            context=context,
            identity=identity,
            title=title,
            description=description,
            trigger_at=trigger_at,
        )

    if action == "cancel":
        return await _cancel_action(context=context, task_id=task_id)

    return await _list_action(context=context, limit=limit)


async def _create_action(
    *,
    context: AIToolExecutionContext,
    identity: "ChatSessionIdentity",
    title: str | None,
    description: str | None,
    trigger_at: str | None,
) -> AIToolResult:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput

    if description is None:
        return _error_result("create", "description is required for create")

    parsed_trigger = _parse_iso_datetime(trigger_at)
    if parsed_trigger is None:
        return _error_result(
            "create",
            "trigger_at must be an absolute ISO datetime with timezone",
        )

    future_tasks = _resolve_future_tasks_entry()
    result = await future_tasks.create_task(
        AIFutureTaskCreateInput(
            session_id=identity.session_id,
            platform=identity.platform,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
            user_id=identity.subject_id,
            title=title or description[:32],
            description=description,
            trigger_at=parsed_trigger,
            source_message_id=context.source_message_id,
        ),
    )
    message = (
        _build_confirmation_message(result.task)
        if result.task.status == "pending"
        else _build_schedule_failed_message(result.task)
    )
    return _build_result(
        action="create",
        ok=result.task.status == "pending",
        message=message,
        tasks=(result.task,),
    )


async def _cancel_action(
    *,
    context: AIToolExecutionContext,
    task_id: str | None,
) -> AIToolResult:
    if task_id is None:
        return _error_result("cancel", "task_id is required for cancel")

    future_tasks = _resolve_future_tasks_entry()
    existing = await future_tasks.get_task(task_id=task_id)
    if existing is None:
        return _error_result("cancel", f"task {task_id} was not found")
    if existing.session_id != context.session_id:
        return _error_result("cancel", "task does not belong to the current session")

    cancelled = await future_tasks.cancel_task(task_id=task_id)
    if cancelled is None:
        return _error_result("cancel", f"task {task_id} was not found")

    return _build_result(
        action="cancel",
        ok=True,
        message=f"cancelled task {task_id}",
        tasks=(cancelled,),
    )


async def _list_action(
    *,
    context: AIToolExecutionContext,
    limit: int | None,
) -> AIToolResult:
    tasks = await _resolve_future_tasks_entry().list_tasks(
        limit=max(1, min(limit or 5, 10)),
        session_id=context.session_id,
    )
    if not tasks:
        return _build_result(
            action="list",
            ok=True,
            message="no future tasks in this session",
        )

    return _build_result(
        action="list",
        ok=True,
        message=f"listed {len(tasks)} future tasks",
        tasks=tuple(tasks),
    )


def _error_result(action: _FutureTaskAction, message: str) -> AIToolResult:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskToolOutput

    output = AIFutureTaskToolOutput(action=action, ok=False, message=message)
    return AIToolResult(
        summary=f"- [future_task.manage] failed: {message}",
        output_payload=output,
        status="error",
    )


def _build_result(
    *,
    action: _FutureTaskAction,
    ok: bool,
    message: str,
    tasks: tuple["AIFutureTaskDefinition", ...] = (),
) -> AIToolResult:
    from apeiria.app.ai.future_tasks.models import (
        AIFutureTaskToolItem,
        AIFutureTaskToolOutput,
    )

    tool_items = tuple(
        AIFutureTaskToolItem(
            task_id=t.task_id,
            title=t.title,
            description=t.description,
            trigger_at=t.trigger_at,
            status=t.status,
        )
        for t in tasks
    )
    output = AIFutureTaskToolOutput(
        action=action,
        ok=ok,
        message=message,
        tasks=tool_items or (),
    )
    summary = f"- [future_task.manage] {message}"
    if tool_items:
        task_text = "; ".join(
            f"{t.task_id} ({t.status}) at {t.trigger_at.isoformat()}: {t.description}"
            for t in tool_items
        )
        summary = f"{summary}. {task_text}"
    return AIToolResult(
        summary=summary,
        output_payload=output,
        status="success" if ok else "error",
    )


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


def _resolve_future_tasks_entry() -> "AIFutureTasksEntry":
    from apeiria.app.ai import ai_application

    return cast("AIFutureTasksEntry", ai_application.future_tasks)


def _build_confirmation_message(task: "AIFutureTaskDefinition") -> str:
    from apeiria.app.ai.future_tasks.service import AIFutureTaskService

    return AIFutureTaskService.build_confirmation_message(task)


def _build_schedule_failed_message(task: "AIFutureTaskDefinition") -> str:
    from apeiria.app.ai.future_tasks.service import AIFutureTaskService

    return AIFutureTaskService.build_schedule_failed_message(task)


__all__ = ["handle_future_task"]
