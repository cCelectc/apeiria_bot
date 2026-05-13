from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_MAX_DIAGNOSTIC_LENGTH = 200
_ROUTE_LIMIT = 7
_TOOL_LIST_LIMIT = 3


def test_future_tasks_are_runtime_scheduling_state(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
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
    import apeiria.app.ai.future_tasks.execution as execution_module
    import apeiria.app.ai.future_tasks.service as future_task_module
    from apeiria.app.ai.future_tasks.execution import execute_future_task
    from apeiria.app.ai.future_tasks.models import AIFutureTaskCreateInput
    from apeiria.app.ai.runtime.entry import CommitResult, RuntimeTraceContext
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
            trace: RuntimeTraceContext | None = None,
        ) -> CommitResult:
            assert trace == RuntimeTraceContext(
                kind="conversation",
                trigger="ai_future_task",
            )
            self.calls.append(task_id)
            return CommitResult(
                reply_text="reminder",
                delivery_status=delivery_status,
                commit_status="committed"
                if delivery_status == "delivered"
                else "partial",
                diagnostics={"delivery_reason": expected_error}
                if expected_error
                else {},
            )

    runtime = FakeRuntimeService()
    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        FakeSchedulerService,
    )
    monkeypatch.setattr(execution_module, "_resolve_ai_runtime", lambda: runtime)

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


def test_future_task_route_uses_application_future_tasks_entry(
    monkeypatch: Any,
) -> None:
    import apeiria.webui.routes.ai.future_tasks as route_module
    from apeiria.access.principal import AuthSession, Principal, PrincipalRole

    task = _future_task_definition(task_id="task-1")

    class FakeFutureTasksEntry:
        def __init__(self) -> None:
            self.cancel_actor: str | None = None

        async def list_tasks(self, *, limit: int, session_id: str | None = None):
            assert limit == _ROUTE_LIMIT
            assert session_id is None
            return [task]

        async def cancel_task(
            self,
            *,
            task_id: str,
            actor_username: str | None = None,
        ):
            self.cancel_actor = actor_username
            assert task_id == "task-1"
            return task

    entry = FakeFutureTasksEntry()
    monkeypatch.setattr(
        route_module, "ai_application", type("App", (), {"future_tasks": entry})()
    )

    async def scenario() -> None:
        listed = await route_module.list_ai_future_tasks(object(), limit=_ROUTE_LIMIT)
        cancelled = await route_module.cancel_ai_future_task(
            AuthSession(
                principal=Principal(
                    principal_kind="webui_account",
                    principal_id="operator-1",
                    display_name="operator",
                    role=PrincipalRole(role_id="admin"),
                ),
                auth_method="bearer_token",
                session_version=1,
                token_subject="operator-1",
            ),
            task_id="task-1",
        )

        assert [item.task_id for item in listed] == ["task-1"]
        assert cancelled is not None
        assert cancelled.task_id == "task-1"
        assert entry.cancel_actor == "operator"

    asyncio.run(scenario())


def test_future_task_tool_handler_uses_application_future_tasks_entry(
    monkeypatch: Any,
) -> None:
    import apeiria.conversation.service as conversation_service_module
    from apeiria.ai.tools.models import (
        AIToolExecutionContext,
        AIToolLevel,
        AIToolPolicy,
    )
    from apeiria.app.ai.future_tasks import tool_handler
    from apeiria.conversation.models import ChatSessionIdentity

    task = _future_task_definition(task_id="task-1")

    class FakeFutureTasksEntry:
        async def list_tasks(self, *, limit: int, session_id: str | None = None):
            assert limit == _TOOL_LIST_LIMIT
            assert session_id == "session-1"
            return [task]

    monkeypatch.setattr(
        tool_handler,
        "_resolve_future_tasks_entry",
        FakeFutureTasksEntry,
    )

    class FakeChatSessionService:
        async def get_session_identity(self, *, session_id: str):
            assert session_id == "session-1"
            return ChatSessionIdentity(
                session_id="session-1",
                platform="test",
                bot_id="bot-1",
                scene_type="private",
                scene_id="scene-1",
                subject_id="user-1",
            )

    monkeypatch.setattr(
        conversation_service_module,
        "chat_session_service",
        FakeChatSessionService(),
    )

    result = asyncio.run(
        tool_handler.handle_future_task(
            "list",
            limit=_TOOL_LIST_LIMIT,
            context=AIToolExecutionContext(
                session_id="session-1",
                source_message_id="message-1",
                trace_id="trace-1",
                message_text="list reminders",
                policy=AIToolPolicy(allowed_level=AIToolLevel.WRITE),
                recalled_memory_ids=(),
                recalled_memory_contents=(),
                relationship_context=None,
                execution_timeout_seconds=None,
            ),
        )
    )

    assert result.status == "success"
    assert result.output_payload is not None
    assert result.output_payload.tasks[0].task_id == "task-1"


def _future_task_definition(
    *,
    task_id: str,
) -> object:
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition

    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    return AIFutureTaskDefinition(
        task_id=task_id,
        session_id="session-1",
        platform="test",
        scene_type="private",
        scene_id="scene-1",
        user_id="user-1",
        title="Wake",
        description="send a reminder",
        trigger_at=now,
        status="pending",
        source_message_id="message-1",
        scheduler_job_id="job-1",
        last_error=None,
        created_at=now,
        updated_at=now,
    )
