"""Scheduler service — wraps APScheduler with registration API."""

from __future__ import annotations

from typing import Any

from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler as _scheduler


class SchedulerService:
    """Wrap APScheduler and expose job inspection helpers."""

    @property
    def raw(self):  # noqa: ANN201
        return _scheduler

    def scheduled_job(
        self,
        trigger: str,
        **kwargs: Any,
    ) -> Any:
        return _scheduler.scheduled_job(trigger, **kwargs)

    def add_job(self, func: Any, trigger: str, **kwargs: Any) -> str:
        job = _scheduler.add_job(func, trigger, **kwargs)
        logger.debug("Scheduled job added: {} ({})", job.id, trigger)
        return str(job.id)

    def remove_job(self, job_id: str) -> None:
        _scheduler.remove_job(job_id)
        logger.debug("Scheduled job removed: {}", job_id)

    def get_jobs(self) -> list[dict[str, Any]]:
        jobs = _scheduler.get_jobs()
        return [
            {
                "id": str(job.id),
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
            }
            for job in jobs
        ]

    def get_job(self, job_id: str) -> Any | None:
        return _scheduler.get_job(job_id)

    def pause_job(self, job_id: str) -> None:
        _scheduler.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        _scheduler.resume_job(job_id)


scheduler_service = SchedulerService()
