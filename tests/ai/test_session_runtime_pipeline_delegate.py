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
