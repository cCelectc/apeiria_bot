"""Future-task runtime execution entrypoint."""

from __future__ import annotations

from nonebot.log import logger


async def execute_future_task(task_id: str) -> None:
    """Wake the AI runtime for one due future task."""

    from apeiria.app.ai.future_task.service import ai_future_task_service

    task = await ai_future_task_service.get_task(task_id=task_id)
    if task is None or task.status != "pending":
        return
    await ai_future_task_service.mark_task_running(task_id=task_id)

    try:
        from apeiria.app.ai.pipeline import AITraceContext
        from apeiria.app.ai.pipeline.service import ai_runtime_service

        runtime_result = await ai_runtime_service.handle_future_task(
            task_id,
            trace=AITraceContext(
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
    elif (
        runtime_result.delivery_result is None
        or not runtime_result.delivery_result.delivered
    ):
        await ai_future_task_service.mark_task_failed(
            task_id=task_id,
            error=(
                runtime_result.delivery_result.error
                if runtime_result.delivery_result is not None
                and runtime_result.delivery_result.error
                else "future task delivery failed"
            ),
        )
    else:
        await ai_future_task_service.mark_task_sent(task_id=task_id)


__all__ = ["execute_future_task"]
