from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_MAX_DIAGNOSTIC_LENGTH = 200


def test_import_app_ai_future_task_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.future_task",
        "apeiria.app.ai.future_task.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.future_task")

    assert module.__name__ == "apeiria.app.ai.future_task"
    assert "ai_future_task_service" in module.__all__
    assert "apeiria.app.ai.future_task.service" not in sys.modules
    assert (
        module.ai_future_task_service
        is sys.modules["apeiria.app.ai.future_task.service"].ai_future_task_service
    )


def test_future_tasks_are_runtime_scheduling_state(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

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


def test_future_tasks_survive_service_reinstantiation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )

    async def scenario() -> None:
        trigger_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        created = await future_task_module.AIFutureTaskService().create_task(
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

        reloaded_service = future_task_module.AIFutureTaskService()
        listed = await reloaded_service.list_tasks(limit=10, session_id="session-1")
        assert [task.task_id for task in listed] == [created.task.task_id]
        assert listed[0].scheduler_job_id == f"job:{created.task.task_id}"

        running = await reloaded_service.claim_task(task_id=created.task.task_id)
        assert running is not None
        assert running.status == "running"

        await reloaded_service.mark_task_failed(
            task_id=created.task.task_id,
            error="delivery failed",
        )
        final_service = future_task_module.AIFutureTaskService()
        failed = await final_service.get_task(task_id=created.task.task_id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.last_error == "delivery failed"

    asyncio.run(scenario())


def test_future_task_failure_error_is_sanitized(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )

    async def scenario() -> None:
        trigger_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        created = await future_task_module.AIFutureTaskService().create_task(
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

        failed = await future_task_module.AIFutureTaskService().mark_task_failed(
            task_id=created.task.task_id,
            error="api_key=sk-secret " + "x" * 400,
        )

        assert failed is not None
        assert failed.last_error is not None
        assert failed.last_error.startswith("api_key=[redacted] ")
        assert len(failed.last_error) == _MAX_DIAGNOSTIC_LENGTH

    asyncio.run(scenario())


def test_future_task_claim_is_idempotent(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )

    async def scenario() -> None:
        trigger_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        created = await future_task_module.AIFutureTaskService().create_task(
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
        service = future_task_module.AIFutureTaskService()

        first_claim = await service.claim_task(task_id=created.task.task_id)
        second_claim = await service.claim_task(task_id=created.task.task_id)

        assert first_claim is not None
        assert first_claim.status == "running"
        assert second_claim is None
        assert (await service.get_task(task_id=created.task.task_id)) == first_claim

    asyncio.run(scenario())


def test_future_task_recovery_reschedules_pending_tasks(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    scheduled: list[dict[str, object]] = []

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            scheduled.append(kwargs)
            return f"job:{kwargs['id']}"

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )

    async def scenario() -> None:
        now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        service = future_task_module.AIFutureTaskService()
        future = await service.create_task(
            AIFutureTaskCreateInput(
                session_id="session-1",
                platform="test",
                scene_type="private",
                scene_id="scene-1",
                user_id="user-1",
                title="Future",
                description="future task",
                trigger_at=now + timedelta(minutes=10),
            )
        )
        due = await service.create_task(
            AIFutureTaskCreateInput(
                session_id="session-1",
                platform="test",
                scene_type="private",
                scene_id="scene-1",
                user_id="user-1",
                title="Due",
                description="due task",
                trigger_at=now - timedelta(minutes=1),
            )
        )
        terminal = await service.create_task(
            AIFutureTaskCreateInput(
                session_id="session-1",
                platform="test",
                scene_type="private",
                scene_id="scene-1",
                user_id="user-1",
                title="Sent",
                description="sent task",
                trigger_at=now,
            )
        )
        await service.mark_task_sent(task_id=terminal.task.task_id)
        scheduled.clear()

        result = await future_task_module.AIFutureTaskService().recover_scheduled_tasks(
            now=now
        )

        assert set(result.rescheduled_task_ids) == {
            future.task.task_id,
            due.task.task_id,
        }
        assert result.failed_task_ids == ()
        run_dates = {item["id"]: item["run_date"] for item in scheduled}
        assert run_dates[future.task.task_id] == future.task.trigger_at
        assert run_dates[due.task.task_id] == now
        assert terminal.task.task_id not in run_dates

    asyncio.run(scenario())


def test_future_task_recovery_marks_stale_running_failed(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )

    async def scenario() -> None:
        now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        service = future_task_module.AIFutureTaskService()
        created = await service.create_task(
            AIFutureTaskCreateInput(
                session_id="session-1",
                platform="test",
                scene_type="private",
                scene_id="scene-1",
                user_id="user-1",
                title="Running",
                description="stale running",
                trigger_at=now - timedelta(minutes=10),
            )
        )
        await service.claim_task(task_id=created.task.task_id)

        result = await future_task_module.AIFutureTaskService().recover_scheduled_tasks(
            now=now
        )

        recovered = await service.get_task(task_id=created.task.task_id)
        assert result.rescheduled_task_ids == ()
        assert result.failed_task_ids == (created.task.task_id,)
        assert recovered is not None
        assert recovered.status == "failed"
        assert recovered.last_error == "stale_running_recovered"
        assert recovered.recovery_reason == "stale_running_recovered"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("delivery_status", "expected_status", "expected_error"),
    [
        ("delivered", "sent", None),
        ("failed", "failed", "bot_not_connected"),
    ],
)
def test_future_task_execution_maps_runtime_delivery_to_durable_completion(
    monkeypatch: Any,
    tmp_path: Path,
    delivery_status: str,
    expected_status: str,
    expected_error: str | None,
) -> None:
    import apeiria.app.ai.future_task.service as future_task_module
    import apeiria.app.ai.pipeline.service as runtime_service_module
    from apeiria.app.ai.future_task.execution import execute_future_task
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyResult
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeSchedulerService:
        def add_job(self, *_: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    class FakeRuntimeService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def handle_future_task(
            self,
            task_id: str,
            *,
            trace: object | None = None,
        ) -> AIRuntimeReplyResult:
            del trace
            self.calls.append(task_id)
            delivered = delivery_status == "delivered"
            return AIRuntimeReplyResult(
                reply_text="reminder",
                delivery_result=DeliveryOutcome(
                    delivered=delivered,
                    reason=None if delivered else "bot_not_connected",
                ),
            )

    runtime = FakeRuntimeService()
    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )
    monkeypatch.setattr(runtime_service_module, "ai_runtime_service", runtime)

    async def scenario() -> None:
        trigger_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        created = await future_task_module.ai_future_task_service.create_task(
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

        await execute_future_task(created.task.task_id)

        final_task = await future_task_module.ai_future_task_service.get_task(
            task_id=created.task.task_id,
        )
        assert runtime.calls == [created.task.task_id]
        assert final_task is not None
        assert final_task.status == expected_status
        assert final_task.last_error == expected_error

    asyncio.run(scenario())
