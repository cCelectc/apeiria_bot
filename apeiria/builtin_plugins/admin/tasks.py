"""Owner-facing scheduler task commands."""

from __future__ import annotations

from apscheduler.jobstores.base import JobLookupError
from arclet.alconna import Args, CommandMeta
from nonebot.adapters import Event  # noqa: TC002
from nonebot_plugin_alconna import Alconna, Match, on_alconna

from apeiria.i18n import t
from apeiria.scheduler import scheduler_service

from .presenter import render_block, render_list_block
from .utils import ensure_owner_message

_tasks = on_alconna(
    Alconna("tasks", meta=CommandMeta(description=t("admin.command.tasks"))),
    use_cmd_start=True,
    priority=5,
    block=True,
)

_task = on_alconna(
    Alconna(
        "task",
        Args["action", str],
        Args["task_id", str],
        meta=CommandMeta(description=t("admin.command.task")),
    ),
    use_cmd_start=True,
    priority=5,
    block=True,
)


@_tasks.handle()
async def handle_tasks(event: Event) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _tasks.finish(owner_error)

    jobs = sorted(scheduler_service.get_jobs(), key=lambda item: item["id"])
    lines = [
        (
            "- {id} | {name} | {next_run} | {trigger}".format(
                id=job["id"],
                name=job["name"],
                next_run=job["next_run_time"] or t("admin.task.paused_state"),
                trigger=job["trigger"],
            )
        )
        for job in jobs
    ]
    await _tasks.finish(
        render_list_block(
            t("admin.tasks.title"),
            lines,
            summary=t("admin.tasks.summary", count=len(jobs)),
            empty_message=t("admin.tasks.empty"),
        )
    )


@_task.handle()
async def handle_task(
    event: Event,
    action: Match[str],
    task_id: Match[str],
) -> None:
    owner_error = ensure_owner_message(event)
    if owner_error:
        await _task.finish(owner_error)

    selected_action = action.result.strip().lower()
    if selected_action not in {"pause", "resume", "info"}:
        await _task.finish(t("admin.task.invalid_action"))

    job = scheduler_service.get_job(task_id.result)
    if job is None:
        await _task.finish(t("admin.task.not_found", task_id=task_id.result))

    if selected_action == "info":
        await _task.finish(_render_task_info(job))

    try:
        if selected_action == "pause":
            if job.next_run_time is None:
                await _task.finish(
                    t("admin.task.already_paused", task_id=task_id.result)
                )
            scheduler_service.pause_job(task_id.result)
            await _task.finish(t("admin.task.paused", task_id=task_id.result))

        if job.next_run_time is not None:
            await _task.finish(t("admin.task.already_running", task_id=task_id.result))
        scheduler_service.resume_job(task_id.result)
        await _task.finish(t("admin.task.resumed", task_id=task_id.result))
    except JobLookupError:
        await _task.finish(t("admin.task.not_found", task_id=task_id.result))


def _render_task_info(job: object) -> str:
    return render_block(
        t("admin.task.info_title"),
        [
            (t("admin.task.field_id"), getattr(job, "id", "")),
            (t("admin.task.field_name"), getattr(job, "name", "")),
            (
                t("admin.task.field_next_run"),
                getattr(job, "next_run_time", None) or t("admin.task.paused_state"),
            ),
            (t("admin.task.field_trigger"), getattr(job, "trigger", "")),
            (t("admin.task.field_executor"), getattr(job, "executor", "")),
            (
                t("admin.task.field_max_instances"),
                getattr(job, "max_instances", t("admin.common.none")),
            ),
            (
                t("admin.task.field_misfire_grace"),
                getattr(job, "misfire_grace_time", t("admin.common.none")),
            ),
        ],
    )
