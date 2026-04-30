from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from apeiria.ai.model import AIModelMessage
from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.app.ai.session_runtime import (
    AISessionTurnEngine,
    DefaultRuntimeCommitStage,
    RuntimeExecutionOutcome,
    RuntimeHardRuleDecision,
    RuntimeTurnPlan,
    ToolExposurePlan,
)
from apeiria.conversation.models import ChatSessionIdentity


class DatabaseWriteFailedError(RuntimeError):
    pass


class ContextRebuildFailedError(RuntimeError):
    pass


def _request(*, runtime_mode: str = "future_task") -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="onebot",
            bot_id="bot-1",
            scene_type="private",
            scene_id="10001",
            subject_id="10001",
        ),
        message_text="wake",
        source_message_id="message-1",
        user_id="10001",
        sender_id="bot-1",
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
    )


def _plan() -> RuntimeTurnPlan:
    return RuntimeTurnPlan(
        stage="planning",
        selected=object(),  # type: ignore[arg-type]
        fallback_models=(),
        skill_runtime=SimpleNamespace(turns=()),
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={},
        tool_exposure_plan=ToolExposurePlan(),
    )


def _execution() -> RuntimeExecutionOutcome:
    return RuntimeExecutionOutcome(
        stage="execution",
        response=SimpleNamespace(
            content="reminder",
            source_id="source-1",
            model_name="model-1",
        ),
        skill_runtime=SimpleNamespace(turns=()),
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=SimpleNamespace(
            metadata={},
            model_attempts=(),
            tool_attempts=(),
            status="completed",
            finish_reason="direct_model_completed",
            response_source="direct",
        ),
    )


def _hard_decision() -> RuntimeHardRuleDecision:
    return RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("future_task",),
        reason_text="future task",
        evidence={},
        should_observe=True,
        should_reply=True,
    )


class _CommitPersistenceStage:
    def __init__(
        self,
        *,
        fail_assistant_message: bool = False,
        fail_context_window: bool = False,
    ) -> None:
        self.fail_assistant_message = fail_assistant_message
        self.fail_context_window = fail_context_window

    async def persist_tool_observations(self, **_: object) -> str:
        return "not_required"

    async def persist_assistant_message(self, **_: object) -> None:
        if self.fail_assistant_message:
            raise DatabaseWriteFailedError

    async def rebuild_context_window(self, **_: object) -> None:
        if self.fail_context_window:
            raise ContextRebuildFailedError


def test_generation_stage_does_not_own_proactive_delivery() -> None:
    project_root = Path(__file__).resolve().parents[2]
    source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py"
    ).read_text(encoding="utf-8")

    assert "deliver_generated_reply" not in source


def test_commit_records_partial_delivery_failure() -> None:
    deliveries: list[tuple[AIRuntimeReplyRequest, str, str]] = []

    async def deliver_reply(
        request: AIRuntimeReplyRequest,
        reply_text: str,
        *,
        trace_id: str = "",
    ) -> DeliveryOutcome:
        deliveries.append((request, reply_text, trace_id))
        return DeliveryOutcome(
            delivered=False,
            status="failed",
            reason="bot_not_connected",
            channel="onebot",
        )

    engine = AISessionTurnEngine(
        commit_stage=DefaultRuntimeCommitStage(
            reply_persistence=_CommitPersistenceStage(),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
            deliver_reply=deliver_reply,
            record_context_usage=lambda *_args, **_kwargs: None,
        )
    )

    commit = asyncio.run(
        engine.commit_turn(
            request=_request(),
            inputs=SimpleNamespace(turns=[]),
            social_decision=object(),
            plan=_plan(),
            generation=_execution(),
            trace_id="trace-1",
            hard_decision=_hard_decision(),
            current_time=datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc),
            session_runtime=None,
        )
    )

    assert deliveries == [(_request(), "reminder", "trace-1")]
    assert commit.commit_status == "partial"
    assert commit.delivery_result is not None
    assert commit.delivery_result.reason == "bot_not_connected"
    assert commit.substeps["delivery"] == "failed"
    assert commit.substeps["assistant_message"] == "committed"
    assert commit.substeps["context_window"] == "committed"


def test_commit_failure_does_not_rewrite_execution_attempts() -> None:
    engine = AISessionTurnEngine(
        commit_stage=DefaultRuntimeCommitStage(
            reply_persistence=_CommitPersistenceStage(fail_assistant_message=True),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
            deliver_reply=lambda *_args, **_kwargs: None,
            record_context_usage=lambda *_args, **_kwargs: None,
        )
    )

    commit = asyncio.run(
        engine.commit_turn(
            request=_request(runtime_mode="message"),
            inputs=SimpleNamespace(turns=[]),
            social_decision=object(),
            plan=_plan(),
            generation=_execution(),
            trace_id="trace-1",
            hard_decision=_hard_decision(),
            current_time=datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc),
            session_runtime=None,
        )
    )

    assert commit.commit_status == "failed"
    assert commit.substeps["assistant_message"] == "failed"
    assert _execution().turn_result.status == "completed"
