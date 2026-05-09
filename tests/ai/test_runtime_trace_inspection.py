from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from apeiria.ai.turn_records import ModelAttempt, PromptSafeObservation, ToolAttempt
from apeiria.app.ai.runtime.trace import TurnTrace
from apeiria.db.runtime import database_runtime

_DEFAULT_TRACE_LIMIT = 20
_HTTP_NOT_FOUND = 404


def test_runtime_admin_service_lists_and_gets_turn_traces(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    from apeiria.app.ai.diagnostics import AIDiagnosticsEntry
    from apeiria.app.ai.runtime.trace import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()
    first = repository.store_trace(
        _trace("trace-1", session_id="session-1", runtime_mode="message"),
        terminal_status="generated",
        commit_status="committed",
    )
    second = repository.store_trace(
        _trace("trace-2", session_id="session-2", runtime_mode="future_task"),
        terminal_status="delivery_failed",
        commit_status="partial",
    )
    service = AIDiagnosticsEntry(trace_repository=repository)

    async def scenario() -> None:
        assert await service.list_turn_traces(limit=10) == [second, first]
        assert await service.list_turn_traces(
            limit=10,
            runtime_mode="future_task",
        ) == [second]
        assert await service.get_turn_trace(trace_id="trace-1") == first
        assert await service.get_turn_trace(trace_id="missing") is None

    asyncio.run(scenario())


def test_ai_trace_routes_return_sanitized_compact_records(monkeypatch: Any) -> None:
    import apeiria.webui.routes.ai.traces as route_module
    from apeiria.app.ai.runtime.trace import TurnTraceRecord

    record = TurnTraceRecord(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="message",
        terminal_status="generated",
        strategy_action="continue",
        strategy_reason_codes=("direct_signal",),
        model_attempt_count=1,
        tool_attempt_count=1,
        final_response_source="direct",
        skip_reason=None,
        delivery_status=None,
        commit_status="committed",
        diagnostics={"api_key": "[redacted]"},
        created_at=datetime.fromisoformat("2026-05-01T08:30:00+00:00"),
    )

    class FakeService:
        async def list_turn_traces(self, **kwargs: object) -> list[TurnTraceRecord]:
            assert kwargs["limit"] == _DEFAULT_TRACE_LIMIT
            assert kwargs["session_id"] == "session-1"
            return [record]

        async def get_turn_trace(self, *, trace_id: str) -> TurnTraceRecord | None:
            assert trace_id == "trace-1"
            return record

    monkeypatch.setattr(
        route_module,
        "ai_application",
        type("FakeApplication", (), {"diagnostics": FakeService()})(),
    )

    async def scenario() -> None:
        listed = await route_module.list_ai_turn_traces(
            object(),
            limit=_DEFAULT_TRACE_LIMIT,
            session_id="session-1",
        )
        loaded = await route_module.get_ai_turn_trace("trace-1", object())

        assert listed == [loaded]
        assert loaded.trace_id == "trace-1"
        assert loaded.diagnostics == {"api_key": "[redacted]"}
        assert loaded.created_at == "2026-05-01T08:30:00+00:00"


def test_ai_trace_route_keeps_bounded_reasoning_metadata(monkeypatch: Any) -> None:
    import apeiria.webui.routes.ai.traces as route_module
    from apeiria.app.ai.runtime.trace import TurnTraceRecord

    record = TurnTraceRecord(
        trace_id="trace-2",
        session_id="session-1",
        runtime_mode="message",
        terminal_status="generated",
        strategy_action="continue",
        strategy_reason_codes=("direct_signal",),
        model_attempt_count=1,
        tool_attempt_count=0,
        final_response_source="direct",
        skip_reason=None,
        delivery_status=None,
        commit_status="committed",
        diagnostics={
            "reasoning": [
                {
                    "requested_effort": "medium",
                    "applied_effort": "medium",
                    "provider_reasoning_present": True,
                    "visible_reasoning_stripped": True,
                }
            ]
        },
        created_at=datetime.fromisoformat("2026-05-01T08:30:00+00:00"),
    )

    class FakeService:
        async def list_turn_traces(self, **_kwargs: object) -> list[TurnTraceRecord]:
            return [record]

        async def get_turn_trace(self, *, trace_id: str) -> TurnTraceRecord | None:
            return record if trace_id == "trace-2" else None

    monkeypatch.setattr(
        route_module,
        "ai_application",
        type("FakeApplication", (), {"diagnostics": FakeService()})(),
    )

    async def scenario() -> None:
        loaded = await route_module.get_ai_turn_trace("trace-2", object())
        assert loaded.diagnostics["reasoning"][0]["visible_reasoning_stripped"] is True

    asyncio.run(scenario())

    asyncio.run(scenario())


def test_ai_trace_route_returns_not_found(monkeypatch: Any) -> None:
    import apeiria.webui.routes.ai.traces as route_module

    class FakeService:
        async def get_turn_trace(self, *, trace_id: str) -> None:
            assert trace_id == "missing"

    monkeypatch.setattr(
        route_module,
        "ai_application",
        type("FakeApplication", (), {"diagnostics": FakeService()})(),
    )

    async def scenario() -> None:
        with pytest.raises(route_module.HTTPException) as exc_info:
            await route_module.get_ai_turn_trace("missing", object())
        assert exc_info.value.status_code == _HTTP_NOT_FOUND
        assert exc_info.value.detail == "trace_not_found"

    asyncio.run(scenario())


def _trace(trace_id: str, *, session_id: str, runtime_mode: str) -> TurnTrace:
    return TurnTrace(
        trace_id=trace_id,
        session_id=session_id,
        runtime_mode=runtime_mode,
        strategy_action="continue",
        strategy_reason_codes=("direct_signal",),
        model_attempts=(
            ModelAttempt(
                attempt_index=1,
                model_ref="source:gpt",
                status="success",
                response_source="direct",
            ),
        ),
        tool_attempts=(
            ToolAttempt(
                tool_call_id="call-1",
                tool_name="memory.query",
                status="success",
                arguments_summary="{}",
                observation=PromptSafeObservation(content="ok"),
            ),
        ),
        final_response_source="direct",
    )
