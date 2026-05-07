from __future__ import annotations

import asyncio
from dataclasses import dataclass, fields
from typing import Any, cast

import pytest

from apeiria.app.ai.runtime.entry import (
    AcceptedTurn,
    AIRuntimeEntry,
    CommitResult,
    RuntimeInput,
    RuntimeTraceContext,
    RuntimeTraceRecordInput,
    TurnContextMaterials,
    TurnExecutionResult,
    TurnPlan,
    TurnTrace,
)


@dataclass
class _StageLog:
    calls: list[str]


class _IngressStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def accept_message(self, bot: object, event: object) -> RuntimeInput:
        assert bot == "bot"
        assert event == "event"
        self._log.calls.append("ingress")
        return RuntimeInput(
            source_type="message",
            message_text="hello",
            session_id="session-1",
            user_id="user-1",
            sender_id="bot-1",
        )

    async def accept_future_task(self, task_id: str) -> RuntimeInput:
        assert task_id == "task-1"
        self._log.calls.append("ingress")
        return RuntimeInput(
            source_type="future_task",
            message_text="remind",
            session_id="session-1",
            user_id="user-1",
            sender_id="bot-1",
            runtime_mode="future_task",
        )


class _SessionStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def accept(
        self,
        runtime_input: RuntimeInput,
        *,
        trace_id: str,
    ) -> AcceptedTurn:
        assert runtime_input.session_id == "session-1"
        assert trace_id.startswith("ai_trace_")
        self._log.calls.append("session")
        return AcceptedTurn(
            turn_id=trace_id,
            input=runtime_input,
            lifecycle_state="accepted",
        )


class _ContextStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def assemble(self, accepted_turn: AcceptedTurn) -> TurnContextMaterials:
        assert accepted_turn.session_id == "session-1"
        self._log.calls.append("context")
        return TurnContextMaterials(
            summary="context-ready",
            messages=("hello",),
        )


class _PlanningStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def plan(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
    ) -> TurnPlan | None:
        assert accepted_turn.session_id == "session-1"
        assert context.summary == "context-ready"
        self._log.calls.append("planning")
        return TurnPlan(
            reply_decision="reply",
            model_selection="model-1",
            prompt_messages=("hello",),
        )


class _ExecutionStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def execute(
        self,
        accepted_turn: AcceptedTurn,
        plan: TurnPlan,
    ) -> TurnExecutionResult:
        assert accepted_turn.session_id == "session-1"
        assert plan.model_selection == "model-1"
        self._log.calls.append("execution")
        return TurnExecutionResult(reply_text="hello")


class _CommitStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    async def commit(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
        plan: TurnPlan,
        execution: TurnExecutionResult,
    ) -> CommitResult:
        assert accepted_turn.session_id == "session-1"
        assert context.summary == "context-ready"
        assert plan.model_selection == "model-1"
        assert execution.reply_text == "hello"
        self._log.calls.append("commit")
        return CommitResult(reply_text=execution.reply_text)


class _TraceStage:
    def __init__(self, log: _StageLog) -> None:
        self._log = log

    def record(self, trace_input: RuntimeTraceRecordInput) -> None:
        assert trace_input.accepted_turn is not None
        assert trace_input.accepted_turn.session_id == "session-1"
        assert trace_input.trace.kind == "test"
        assert trace_input.context is not None
        assert trace_input.context.summary == "context-ready"
        if trace_input.plan is None:
            assert trace_input.execution is None
            assert trace_input.commit is None
        else:
            assert trace_input.plan.model_selection == "model-1"
            assert trace_input.execution is not None
            assert trace_input.execution.reply_text == "hello"
            assert trace_input.commit is not None
            assert trace_input.commit.reply_text == "hello"
        self._log.calls.append("trace")


def test_runtime_entry_runs_message_turn_in_new_stage_order() -> None:
    asyncio.run(_assert_runtime_entry_runs_message_turn_in_new_stage_order())


async def _assert_runtime_entry_runs_message_turn_in_new_stage_order() -> None:
    log = _StageLog(calls=[])
    entry = AIRuntimeEntry(
        ingress=_IngressStage(log),
        session=_SessionStage(log),
        context=_ContextStage(log),
        planning=_PlanningStage(log),
        execution=_ExecutionStage(log),
        commit=_CommitStage(log),
        trace=_TraceStage(log),
    )

    reply = await entry.handle_message(
        "bot",
        "event",
        trace=RuntimeTraceContext(kind="test", trigger="unit"),
    )

    assert reply == "hello"
    assert log.calls == [
        "ingress",
        "session",
        "context",
        "planning",
        "execution",
        "commit",
        "trace",
    ]


def test_runtime_entry_short_circuits_when_planning_returns_no_plan() -> None:
    asyncio.run(_assert_runtime_entry_short_circuits_when_planning_returns_no_plan())


async def _assert_runtime_entry_short_circuits_when_planning_returns_no_plan() -> None:
    class _NoReplyPlanningStage(_PlanningStage):
        async def plan(
            self,
            accepted_turn: AcceptedTurn,
            context: TurnContextMaterials,
        ) -> None:
            await super().plan(accepted_turn, context)

    log = _StageLog(calls=[])
    entry = AIRuntimeEntry(
        ingress=_IngressStage(log),
        session=_SessionStage(log),
        context=_ContextStage(log),
        planning=_NoReplyPlanningStage(log),
        execution=_ExecutionStage(log),
        commit=_CommitStage(log),
        trace=_TraceStage(log),
    )

    reply = await entry.handle_message(
        "bot",
        "event",
        trace=RuntimeTraceContext(kind="test", trigger="unit"),
    )

    assert reply is None
    assert log.calls == ["ingress", "session", "context", "planning", "trace"]


def test_runtime_entry_runs_future_task_turn_in_new_stage_order() -> None:
    asyncio.run(_assert_runtime_entry_runs_future_task_turn_in_new_stage_order())


async def _assert_runtime_entry_runs_future_task_turn_in_new_stage_order() -> None:
    log = _StageLog(calls=[])
    entry = AIRuntimeEntry(
        ingress=_IngressStage(log),
        session=_SessionStage(log),
        context=_ContextStage(log),
        planning=_PlanningStage(log),
        execution=_ExecutionStage(log),
        commit=_CommitStage(log),
        trace=_TraceStage(log),
    )

    result = await entry.handle_future_task(
        "task-1",
        trace=RuntimeTraceContext(kind="test", trigger="unit"),
    )

    assert result is not None
    assert result.reply_text == "hello"
    assert log.calls == [
        "ingress",
        "session",
        "context",
        "planning",
        "execution",
        "commit",
        "trace",
    ]


def test_runtime_entry_does_not_expose_old_pipeline_names() -> None:
    import apeiria.app.ai.runtime.entry as module

    assert "AIRuntimeTurnRequest" not in module.__all__
    assert "RuntimeContextInputBundle" not in module.__all__
    assert "AITraceContext" not in module.__all__
    assert not hasattr(AIRuntimeEntry, "_run_reply_pipeline")
    assert not hasattr(AIRuntimeEntry, "_run_reply_pipeline_turn")


def test_runtime_handoff_records_are_bounded_and_immutable() -> None:
    expected_fields = {
        RuntimeInput: {
            "source_type",
            "message_text",
            "session_id",
            "user_id",
            "sender_id",
            "source_message_id",
            "runtime_mode",
            "priority",
            "dedupe_key",
            "metadata",
        },
        AcceptedTurn: {
            "turn_id",
            "input",
            "lifecycle_state",
            "accepted_at",
            "diagnostics",
        },
        TurnContextMaterials: {
            "summary",
            "messages",
            "memories",
            "persona",
            "relationship",
            "tools",
            "diagnostics",
        },
        TurnPlan: {
            "reply_decision",
            "model_selection",
            "fallback_models",
            "prompt_messages",
            "prompt_diagnostics",
            "skill_selection",
            "tool_exposure",
            "execution_mode",
        },
        TurnExecutionResult: {
            "reply_text",
            "model_attempts",
            "tool_attempts",
            "finish_reason",
            "response_source",
            "diagnostics",
        },
        CommitResult: {
            "reply_text",
            "commit_status",
            "delivery_status",
            "substeps",
            "diagnostics",
        },
        TurnTrace: {
            "turn_id",
            "terminal_status",
            "runtime_mode",
            "commit_status",
            "delivery_status",
            "diagnostics",
        },
    }

    for record_type, allowed_fields in expected_fields.items():
        assert record_type.__dataclass_params__.frozen
        actual_fields = {field.name for field in fields(record_type)}
        assert actual_fields == allowed_fields
        assert "payload" not in actual_fields
        assert "raw_context" not in actual_fields


def test_runtime_handoff_record_mappings_are_read_only() -> None:
    runtime_input = RuntimeInput(
        source_type="message",
        message_text="hello",
        session_id="session-1",
        user_id="user-1",
        sender_id="bot-1",
        metadata={"temporary": True},
    )
    accepted = AcceptedTurn(
        turn_id="turn-1",
        input=runtime_input,
        lifecycle_state="accepted",
        diagnostics={"stage": "session"},
    )
    plan = TurnPlan(
        reply_decision="reply",
        prompt_diagnostics={"region_count": 1},
    )

    with pytest.raises(TypeError):
        cast("Any", runtime_input.metadata)["extra"] = False
    with pytest.raises(TypeError):
        cast("Any", accepted.diagnostics)["stage"] = "planning"
    with pytest.raises(TypeError):
        cast("Any", plan.prompt_diagnostics)["region_count"] = 2
