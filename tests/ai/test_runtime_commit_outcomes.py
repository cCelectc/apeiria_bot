from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import apeiria.app.ai.runtime.commit.delivery as delivery_steps
from apeiria.ai.model import AIModelBindingTarget, AIModelMessage
from apeiria.ai.model.runtime.adapter import AIModelGenerateResponse
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.app.ai.runtime.commit import RuntimeCommitEffectsStage
from apeiria.app.ai.runtime.commit.delivery import DeliveryOutcome
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest
from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
)
from apeiria.app.ai.runtime.stages import (
    RuntimeCommitInput,
    RuntimeExecutionOutcome,
    RuntimeTurnPlan,
)
from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
from apeiria.conversation.models import ChatSessionIdentity

if TYPE_CHECKING:
    from pathlib import Path


class DatabaseWriteFailedError(RuntimeError):
    pass


class ContextRebuildFailedError(RuntimeError):
    pass


def _request(
    *,
    runtime_mode: str = "future_task",
    future_task: AIFutureTaskDefinition | None = None,
) -> AIRuntimeTurnRequest:
    return AIRuntimeTurnRequest(
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
        future_task=future_task,
    )


def _future_task() -> AIFutureTaskDefinition:
    now = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
    return AIFutureTaskDefinition(
        task_id="task-1",
        session_id="session-1",
        platform="onebot",
        scene_type="private",
        scene_id="10001",
        user_id="10001",
        title="Wake",
        description="wake",
        trigger_at=now,
        status="running",
        source_message_id="message-1",
        scheduler_job_id=None,
        last_error=None,
        created_at=now,
        updated_at=now,
    )


def _plan() -> RuntimeTurnPlan:
    return RuntimeTurnPlan(
        stage="planning",
        selected=object(),  # type: ignore[arg-type]
        fallback_models=(),
        skill_runtime=RuntimeToolLoopResult(
            policy_text="No tools.",
            result_lines=(),
            turns=(),
        ),
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
        skill_runtime=RuntimeToolLoopResult(
            policy_text="No tools.",
            result_lines=(),
            turns=(),
        ),
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=AgentTurnResult(
            trace_id="trace-1",
            runtime_mode="future_task",
            status="completed",
            finish_reason="direct_model_completed",
            response_source="direct",
        ),
    )


def _think_execution() -> RuntimeExecutionOutcome:
    response = AIModelGenerateResponse(
        source_id="source-1",
        model_name="model-1",
        content="visible <think>hidden reasoning</think> reply",
    )
    return RuntimeExecutionOutcome(
        stage="execution",
        response=response,
        skill_runtime=RuntimeToolLoopResult(
            policy_text="No tools.",
            result_lines=(),
            turns=(),
        ),
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=AgentTurnResult(
            trace_id="trace-1",
            runtime_mode="future_task",
            status="completed",
            finish_reason="direct_model_completed",
            response=response,
            response_source="direct",
        ),
    )


def _context_materials() -> RuntimeContextMaterials:
    return RuntimeContextMaterials(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="10001",
        ),
        tool_policy=AIToolPolicy(execution_enabled=False),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )


def _social_decision() -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="avoid",
        reason_codes=("direct",),
        reason_text="direct",
        evidence={},
        decision_source="llm",
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


def _commit_input(
    *,
    request: AIRuntimeTurnRequest | None = None,
    generation: RuntimeExecutionOutcome | None = None,
) -> RuntimeCommitInput:
    reply_request = request or _request()
    return RuntimeCommitInput(
        stage="commit",
        trace_id="trace-1",
        turn=reply_request.to_runtime_turn_input(),
        context=_context_materials(),
        social_decision=_social_decision(),
        plan=_plan(),
        generation=generation or _execution(),
        hard_decision=_hard_decision(),
        current_time=datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc),
        session_runtime=None,
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
        self.assistant_texts: list[str] = []

    async def persist_tool_observations(self, **_: object) -> str:
        return "not_required"

    async def persist_assistant_message(self, **kwargs: object) -> None:
        response = kwargs.get("generation")
        if response is not None:
            message_response = getattr(response, "response", None)
            if message_response is not None:
                self.assistant_texts.append(getattr(message_response, "content", ""))
        if self.fail_assistant_message:
            raise DatabaseWriteFailedError

    async def rebuild_context_window(self, **_: object) -> None:
        if self.fail_context_window:
            raise ContextRebuildFailedError


def test_commit_records_partial_delivery_failure() -> None:
    deliveries: list[tuple[RuntimeTurnInput, str, str]] = []

    async def deliver_reply(
        turn: RuntimeTurnInput,
        reply_text: str,
        *,
        trace_id: str = "",
    ) -> DeliveryOutcome:
        deliveries.append((turn, reply_text, trace_id))
        return DeliveryOutcome(
            delivered=False,
            status="failed",
            reason="bot_not_connected",
            channel="onebot",
        )

    engine = AISessionTurnEngine(
        commit_stage=RuntimeCommitEffectsStage(
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
            commit_input=_commit_input(),
        )
    )

    assert deliveries == [(_request().to_runtime_turn_input(), "reminder", "trace-1")]
    assert commit.commit_status == "partial"
    assert commit.delivery_result is not None
    assert commit.delivery_result.reason == "bot_not_connected"
    assert commit.substeps["delivery"] == "failed"
    assert commit.substeps["assistant_message"] == "committed"
    assert commit.substeps["context_window"] == "committed"


def test_commit_strips_think_tags_before_delivery_and_persistence() -> None:
    deliveries: list[str] = []
    persistence = _CommitPersistenceStage()

    async def deliver_reply(
        _turn: RuntimeTurnInput,
        reply_text: str,
        *,
        trace_id: str = "",
    ) -> DeliveryOutcome:
        del trace_id
        deliveries.append(reply_text)
        return DeliveryOutcome(delivered=True)

    engine = AISessionTurnEngine(
        commit_stage=RuntimeCommitEffectsStage(
            reply_persistence=persistence,
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
            deliver_reply=deliver_reply,
            record_context_usage=lambda *_args, **_kwargs: None,
        )
    )

    commit = asyncio.run(
        engine.commit_turn(
            commit_input=_commit_input(generation=_think_execution()),
        )
    )

    assert deliveries == ["visible  reply"]
    assert persistence.assistant_texts == ["visible  reply"]
    assert "hidden reasoning" not in str(commit)


def test_commit_failure_does_not_rewrite_execution_attempts() -> None:
    engine = AISessionTurnEngine(
        commit_stage=RuntimeCommitEffectsStage(
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
            commit_input=_commit_input(request=_request(runtime_mode="message")),
        )
    )

    assert commit.commit_status == "failed"
    assert commit.substeps["assistant_message"] == "failed"
    turn_result = _execution().turn_result
    assert turn_result is not None
    assert turn_result.status == "completed"


def test_delivered_attempt_survives_later_commit_failure(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from apeiria.app.ai.future_tasks.delivery_attempts import (
        delivery_attempt_repository,
    )
    from apeiria.db.runtime import database_runtime

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    class FakeGateway:
        async def deliver(
            self,
            _request: delivery_steps.DeliveryRequest,
        ) -> delivery_steps.DeliveryOutcome:
            return delivery_steps.DeliveryOutcome(
                delivered=True,
                channel="onebot",
                remote_message_id="123",
            )

    monkeypatch.setattr(delivery_steps, "delivery_gateway", FakeGateway())
    engine = AISessionTurnEngine(
        commit_stage=RuntimeCommitEffectsStage(
            reply_persistence=_CommitPersistenceStage(fail_assistant_message=True),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
            deliver_reply=delivery_steps.deliver_generated_reply,
            record_context_usage=lambda *_args, **_kwargs: None,
        )
    )

    commit = asyncio.run(
        engine.commit_turn(
            commit_input=_commit_input(request=_request(future_task=_future_task())),
        )
    )
    attempt = delivery_attempt_repository.get_delivered_attempt(
        task_id="task-1",
        delivery_intent="future_task:task-1:reply",
    )

    assert commit.commit_status == "failed"
    assert commit.substeps["delivery"] == "committed"
    assert commit.substeps["assistant_message"] == "failed"
    assert attempt is not None
    assert attempt.status == "delivered"
    assert attempt.remote_message_id == "123"
