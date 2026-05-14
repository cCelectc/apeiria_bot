"""Future-task runtime execution entrypoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from nonebot.log import logger

from apeiria.app.ai.runtime.contracts import RuntimeTraceContext

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.factory import LiveRuntimeEntry


async def execute_future_task(task_id: str) -> None:
    """Wake the AI runtime for one due future task."""

    from apeiria.app.ai.future_tasks.service import ai_future_task_service

    task = await ai_future_task_service.get_task(task_id=task_id)
    if task is None or task.status != "pending":
        return
    claimed = await ai_future_task_service.claim_task(task_id=task_id)
    if claimed is None:
        return

    try:
        runtime_result = await _resolve_ai_runtime().handle_future_task(
            task_id,
            trace=RuntimeTraceContext(
                kind="conversation",
                trigger="ai_future_task",
            ),
        )
    except Exception as exc:  # noqa: BLE001
        await ai_future_task_service.mark_task_failed(
            task_id=task_id,
            error=str(exc),
        )
        logger.opt(exception=exc).warning(
            "Failed to execute AI future task {}",
            task_id,
        )
        return

    task = await ai_future_task_service.get_task(task_id=task_id)
    if task is None or task.status != "running":
        return
    if runtime_result is None:
        await ai_future_task_service.mark_task_failed(
            task_id=task_id,
            error="future task runtime produced no reply",
        )
    elif runtime_result.delivery_status not in {"committed", "delivered"}:
        await ai_future_task_service.mark_task_failed(
            task_id=task_id,
            error=(
                str(runtime_result.diagnostics.get("delivery_reason"))
                if runtime_result.diagnostics.get("delivery_reason")
                else "future task delivery failed"
            ),
        )
    else:
        await ai_future_task_service.mark_task_sent(task_id=task_id)


__all__ = ["execute_future_task"]


def _resolve_ai_runtime() -> "LiveRuntimeEntry":
    from apeiria.app.ai import ai_application

    return cast("LiveRuntimeEntry", ai_application.runtime)
