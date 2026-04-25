from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
from datetime import datetime, timezone
from typing import Any


def test_future_task_service_import_is_safe_without_nonebot_plugin_orm() -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globalns: dict[str, object] | None = None,
        localns: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "nonebot_plugin_orm":
            raise AssertionError(name)
        return original_import(name, globalns, localns, fromlist, level)

    sys.modules.pop("apeiria.ai.future_task.service", None)
    builtins.__import__ = guarded_import
    try:
        module = importlib.import_module("apeiria.ai.future_task.service")
    finally:
        builtins.__import__ = original_import

    assert module.__name__ == "apeiria.ai.future_task.service"


def test_future_tasks_are_runtime_scheduling_state(monkeypatch: Any) -> None:
    import apeiria.ai.future_task.service as future_task_module
    from apeiria.ai.future_task.models import AIFutureTaskCreateInput

    removed_jobs: list[str] = []

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

        def remove_job(self, job_id: str) -> None:
            removed_jobs.append(job_id)

    fake_scheduler = FakeSchedulerService()

    def get_fake_scheduler() -> FakeSchedulerService:
        return fake_scheduler

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        get_fake_scheduler,
    )

    async def scenario() -> None:
        service = future_task_module.AIFutureTaskService()
        trigger_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)

        created = await service.create_task(
            AIFutureTaskCreateInput(
                session_id="session-1",
                platform="test",
                scene_type="private",
                scene_id="scene-1",
                user_id="user-1",
                title="Wake",
                description="send a reminder",
                trigger_at=trigger_at,
                source_message_id="message-1",
            )
        )

        assert created.scheduler_job_id == f"job:{created.task.task_id}"
        assert created.task.status == "pending"
        assert created.task.trigger_at == trigger_at

        listed = await service.list_tasks(limit=10, session_id="session-1")
        assert listed == [created.task]

        running = await service.mark_task_running(task_id=created.task.task_id)
        assert running is not None
        assert running.status == "running"

        failed = await service.mark_task_failed(
            task_id=created.task.task_id,
            error="delivery failed",
        )
        assert failed is not None
        assert failed.status == "failed"
        assert failed.last_error == "delivery failed"

        cancelled = await service.cancel_task(task_id=created.task.task_id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        assert removed_jobs == [created.scheduler_job_id]

    asyncio.run(scenario())
