from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeService,
    AITraceContext,
)
from apeiria.app.ai.session_runtime import RuntimeCommitResult
from apeiria.conversation.models import ChatSessionIdentity


class _SerializedRuntime:
    def __init__(self) -> None:
        self.calls: list[datetime] = []

    async def run_serialized(self, operation: Any, *, now: datetime) -> object:
        self.calls.append(now)
        return await operation()


class _Resolver:
    def __init__(self, runtime: _SerializedRuntime) -> None:
        self.runtime = runtime
        self.resolved: list[tuple[str, datetime]] = []

    def resolve(self, session_id: str, *, now: datetime) -> _SerializedRuntime:
        self.resolved.append((session_id, now))
        return self.runtime


class _Engine:
    def __init__(
        self,
        *,
        commit_result: RuntimeCommitResult | None,
    ) -> None:
        self.commit_result = commit_result
        self.calls: list[AIRuntimeReplyRequest] = []

    async def run_reply_turn(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: AITraceContext,
        request: AIRuntimeReplyRequest,
        wake_context: object | None = None,
        current_time: datetime,
        session_runtime: object | None = None,
    ) -> RuntimeCommitResult | None:
        del trace_id, trace, wake_context, current_time, session_runtime
        self.calls.append(request)
        return self.commit_result


def _request() -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type="private",
            scene_id="user-1",
            subject_id=None,
        ),
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="message",
    )


def _future_task_identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )


@pytest.mark.parametrize(
    "commit_result",
    [
        RuntimeCommitResult(
            stage="commit",
            reply_text="hello back",
            delivery_result=None,
        ),
        None,
    ],
)
def test_reply_pipeline_delegates_to_engine(
    commit_result: RuntimeCommitResult | None,
) -> None:
    runtime = _SerializedRuntime()
    resolver = _Resolver(runtime)
    engine = _Engine(commit_result=commit_result)
    service = AIRuntimeService(
        session_runtime_resolver=resolver,
        turn_engine=engine,  # type: ignore[arg-type]
    )
    request = _request()

    result = asyncio.run(
        service._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=request,
        )
    )

    assert (result.reply_text if result is not None else None) == (
        commit_result.reply_text if commit_result is not None else None
    )
    assert engine.calls == [request]
    assert len(resolver.resolved) == 1
    assert resolver.resolved[0][0] == "session-1"
    assert runtime.calls == []


def test_turn_engine_owns_session_serialization() -> None:
    class _SerializingEngine(_Engine):
        async def run_reply_turn(  # noqa: PLR0913
            self,
            *,
            trace_id: str,
            trace: AITraceContext,
            request: AIRuntimeReplyRequest,
            wake_context: object | None = None,
            current_time: datetime,
            session_runtime: object | None = None,
        ) -> RuntimeCommitResult | None:
            del trace_id, trace, wake_context

            async def operation() -> RuntimeCommitResult | None:
                self.calls.append(request)
                return self.commit_result

            assert session_runtime is not None
            return await session_runtime.run_serialized(operation, now=current_time)

    runtime = _SerializedRuntime()
    resolver = _Resolver(runtime)
    engine = _SerializingEngine(
        commit_result=RuntimeCommitResult(
            stage="commit",
            reply_text="hello back",
            delivery_result=None,
        )
    )
    service = AIRuntimeService(
        session_runtime_resolver=resolver,
        turn_engine=engine,  # type: ignore[arg-type]
    )

    result = asyncio.run(
        service._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=_request(),
        )
    )

    assert result is not None
    assert result.reply_text == "hello back"
    assert engine.calls == [_request()]
    assert len(runtime.calls) == 1
    assert runtime.calls[0].tzinfo == timezone.utc


def test_future_task_entrypoint_reuses_session_serialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    import apeiria.app.ai.pipeline.service as service_module
    from apeiria.app.ai.future_task.models import AIFutureTaskCreateInput
    from apeiria.app.ai.future_task.service import ai_future_task_service
    from apeiria.conversation.service import chat_session_service
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    monkeypatch.setattr(
        service_module,
        "ensure_ai_runtime_support_initialized",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        service_module.ai_retention_service,
        "maybe_schedule_cleanup",
        lambda **_kwargs: None,
    )

    class _Scheduler:
        def add_job(self, *_args: object, **kwargs: object) -> str:
            return f"job:{kwargs['id']}"

    import apeiria.app.ai.future_task.service as future_task_module

    monkeypatch.setattr(
        future_task_module,
        "_get_scheduler_service",
        _Scheduler,
    )

    async def scenario() -> None:
        identity = _future_task_identity()
        await chat_session_service.ensure_session(identity)
        created = await ai_future_task_service.create_task(
            AIFutureTaskCreateInput(
                session_id=identity.session_id,
                platform=identity.platform,
                scene_type=identity.scene_type,
                scene_id=identity.scene_id,
                user_id=identity.subject_id,
                title="Wake",
                description="send a reminder",
                trigger_at=datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc),
                source_message_id="message-1",
            )
        )
        await ai_future_task_service.claim_task(task_id=created.task.task_id)

        class _SerializingEngine(_Engine):
            async def run_reply_turn(  # noqa: PLR0913
                self,
                *,
                trace_id: str,
                trace: AITraceContext,
                request: AIRuntimeReplyRequest,
                wake_context: object | None = None,
                current_time: datetime,
                session_runtime: object | None = None,
            ) -> RuntimeCommitResult | None:
                del trace_id, trace, wake_context

                async def operation() -> RuntimeCommitResult | None:
                    self.calls.append(request)
                    return self.commit_result

                assert session_runtime is not None
                return await session_runtime.run_serialized(operation, now=current_time)

        runtime = _SerializedRuntime()
        resolver = _Resolver(runtime)
        engine = _SerializingEngine(
            commit_result=RuntimeCommitResult(
                stage="commit",
                reply_text="reminder sent",
                delivery_result=None,
            )
        )
        service = AIRuntimeService(
            session_runtime_resolver=resolver,
            turn_engine=engine,  # type: ignore[arg-type]
        )

        result = await service.handle_future_task(created.task.task_id)

        assert result is not None
        assert result.reply_text == "reminder sent"
        assert len(resolver.resolved) == 1
        assert resolver.resolved[0][0] == identity.session_id
        assert len(runtime.calls) == 1
        assert engine.calls[0].runtime_mode == "future_task"
        assert engine.calls[0].future_task is not None
        assert engine.calls[0].future_task.task_id == created.task.task_id

    asyncio.run(scenario())
