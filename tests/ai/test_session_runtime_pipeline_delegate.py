from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeReplyResult,
    AIRuntimeService,
    AITraceContext,
)
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


class _DelegatingService(AIRuntimeService):
    def __init__(
        self,
        *,
        resolver: _Resolver,
        reply_result: AIRuntimeReplyResult | None,
    ) -> None:
        super().__init__(session_runtime_resolver=resolver)
        self.reply_result = reply_result
        self.turn_calls: list[AIRuntimeReplyRequest] = []

    async def _run_reply_pipeline_turn(  # noqa: PLR0913
        self,
        *,
        trace_id: str,
        trace: AITraceContext,
        request: AIRuntimeReplyRequest,
        wake_context: object | None = None,
        current_time: datetime,
        session_runtime: object | None = None,
    ) -> AIRuntimeReplyResult | None:
        del trace_id, trace, wake_context, current_time, session_runtime
        self.turn_calls.append(request)
        return self.reply_result


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
    "reply_result",
    [
        AIRuntimeReplyResult(reply_text="hello back"),
        None,
    ],
)
def test_reply_pipeline_delegates_through_session_runtime(
    reply_result: AIRuntimeReplyResult | None,
) -> None:
    runtime = _SerializedRuntime()
    resolver = _Resolver(runtime)
    service = _DelegatingService(resolver=resolver, reply_result=reply_result)
    request = _request()

    result = asyncio.run(
        service._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=request,
        )
    )

    assert result is reply_result
    assert service.turn_calls == [request]
    assert len(resolver.resolved) == 1
    assert resolver.resolved[0][0] == "session-1"
    assert len(runtime.calls) == 1
    assert runtime.calls[0].tzinfo == timezone.utc
