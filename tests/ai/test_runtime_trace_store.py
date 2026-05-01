from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.turn_records import ModelAttempt, PromptSafeObservation, ToolAttempt
from apeiria.app.ai.session_runtime import RuntimeHardRuleDecision, TurnTrace
from apeiria.conversation.models import ChatSessionIdentity
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path


def test_turn_trace_repository_persists_terminal_trace(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()
    trace = TurnTrace(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="future_task",
        strategy_action="continue",
        strategy_reason_codes=("future_task",),
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
                arguments_summary="query=hello",
                observation=PromptSafeObservation(content="ok"),
            ),
        ),
        final_response_source="direct",
        delivery_status="delivered",
    )

    stored = repository.store_trace(
        trace,
        terminal_status="generated",
        commit_status="committed",
        diagnostics={"source": "unit"},
    )
    loaded = repository.get_trace(trace_id="trace-1")

    assert loaded == stored
    assert stored.trace_id == "trace-1"
    assert stored.model_attempt_count == 1
    assert stored.tool_attempt_count == 1
    assert stored.commit_status == "committed"
    assert stored.delivery_status == "delivered"
    assert stored.diagnostics["source"] == "unit"


def test_turn_trace_repository_sanitizes_diagnostics(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()

    stored = repository.store_trace(
        TurnTrace(
            trace_id="trace-secret",
            session_id="session-1",
            runtime_mode="message",
            strategy_action="drop",
            strategy_reason_codes=("policy_denied",),
            skip_reason="policy_denied",
        ),
        terminal_status="skipped",
        diagnostics={
            "api_key": "sk-secret",
            "adapter_error": "Authorization: Bearer sk-secret",
            "nested": {"password": "secret-value"},
            "safe": "x" * 600,
        },
    )

    assert stored.diagnostics["api_key"] == "[redacted]"
    assert stored.diagnostics["adapter_error"] == "Authorization: Bearer [redacted]"
    assert stored.diagnostics["nested"] == {"password": "[redacted]"}
    assert stored.diagnostics["safe"] == "x" * 500


def test_turn_trace_repository_lists_and_filters_compact_traces(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()
    first = repository.store_trace(
        TurnTrace(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="message",
            strategy_action="continue",
            strategy_reason_codes=("direct_signal",),
            final_response_source="direct",
        ),
        terminal_status="generated",
        commit_status="committed",
        diagnostics={"token": "secret-value"},
    )
    second = repository.store_trace(
        TurnTrace(
            trace_id="trace-2",
            session_id="session-2",
            runtime_mode="future_task",
            strategy_action="continue",
            strategy_reason_codes=("future_task",),
            delivery_status="failed",
        ),
        terminal_status="delivery_failed",
        commit_status="partial",
    )

    assert repository.list_traces(limit=10) == [second, first]
    assert repository.list_traces(limit=10, session_id="session-1") == [first]
    assert repository.list_traces(limit=10, runtime_mode="future_task") == [second]
    assert repository.list_traces(limit=10, terminal_status="generated") == [first]
    assert repository.list_traces(limit=10, commit_status="partial") == [second]
    assert repository.list_traces(limit=10, trace_id="trace-1") == [first]
    assert first.diagnostics["token"] == "[redacted]"
    assert repository.get_trace(trace_id="missing") is None


def test_engine_persists_hard_rule_trace_without_assistant_message(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.app.ai.session_runtime import (
        AISessionTurnEngine,
        DefaultRuntimeTraceStage,
    )
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    request = AIRuntimeReplyRequest(
        identity=identity,
        message_text="hello",
        source_message_id="message-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="message",
    )
    decision = RuntimeHardRuleDecision(
        action="drop",
        reason_codes=("policy_denied",),
        reason_text="denied",
        evidence={"source": "test"},
        should_observe=False,
        should_reply=False,
    )
    engine = AISessionTurnEngine(
        trace_stage=DefaultRuntimeTraceStage(trace_store=repository),
    )

    engine.project_trace(
        trace_id="trace-hard-rule",
        request=request,
        strategy_decision=decision,
        turn_result=None,
    )

    stored = repository.get_trace(trace_id="trace-hard-rule")
    assert stored is not None
    assert stored.terminal_status == "skipped"
    assert stored.skip_reason == "policy_denied"
    assert stored.session_id == "session-1"


def test_trace_store_records_terminal_failure_kinds(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.session_runtime.trace_store import TurnTraceRepository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    repository = TurnTraceRepository()
    traces = [
        (
            TurnTrace(
                trace_id="trace-no-model",
                session_id="session-1",
                runtime_mode="message",
                strategy_action="continue",
                strategy_reason_codes=("direct_signal",),
                skip_reason="no_model_selected",
            ),
            "no_model",
            None,
        ),
        (
            TurnTrace(
                trace_id="trace-empty",
                session_id="session-1",
                runtime_mode="message",
                strategy_action="continue",
                strategy_reason_codes=("direct_signal",),
                model_attempts=(
                    ModelAttempt(
                        attempt_index=1,
                        model_ref="source:gpt",
                        status="failed",
                        response_source="direct",
                        reason="empty_response",
                    ),
                ),
                skip_reason="empty_response",
            ),
            "empty_response",
            None,
        ),
        (
            TurnTrace(
                trace_id="trace-delivery",
                session_id="session-1",
                runtime_mode="future_task",
                strategy_action="continue",
                strategy_reason_codes=("future_task",),
                delivery_status="failed",
            ),
            "delivery_failed",
            "partial",
        ),
        (
            TurnTrace(
                trace_id="trace-commit",
                session_id="session-1",
                runtime_mode="message",
                strategy_action="continue",
                strategy_reason_codes=("direct_signal",),
                final_response_source="direct",
            ),
            "commit_failed",
            "failed",
        ),
    ]

    for trace, terminal_status, commit_status in traces:
        repository.store_trace(
            trace,
            terminal_status=terminal_status,
            commit_status=commit_status,
        )

    no_model = repository.get_trace(trace_id="trace-no-model")
    empty = repository.get_trace(trace_id="trace-empty")
    delivery = repository.get_trace(trace_id="trace-delivery")
    commit = repository.get_trace(trace_id="trace-commit")
    assert no_model is not None
    assert no_model.terminal_status == "no_model"
    assert empty is not None
    assert empty.terminal_status == "empty_response"
    assert delivery is not None
    assert delivery.delivery_status == "failed"
    assert delivery.commit_status == "partial"
    assert commit is not None
    assert commit.terminal_status == "commit_failed"
    assert commit.commit_status == "failed"
