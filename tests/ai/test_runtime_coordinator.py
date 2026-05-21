from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from apeiria.ai.model.catalog.models import AIChatModelDefinition
from apeiria.ai.model.routing.bindings import AIModelBindingTarget
from apeiria.ai.model.routing.models import AIModelProfileDefinition
from apeiria.ai.model.routing.selection import AISelectedModel
from apeiria.ai.model.runtime.adapter import AIModelGenerateResponse, AIModelMessage
from apeiria.ai.model.sources.models import AISourceDefinition
from apeiria.ai.tools.models import AIToolPolicy
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
from apeiria.app.ai.runtime.contracts import RuntimeTraceContext
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.orchestrator import (
    AIRuntimeCoordinator,
    ReplyPath,
    ReplyRuntimeRequest,
)
from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
    RuntimeTurnSource,
)
from apeiria.app.ai.runtime.stages import (
    RuntimeCommitResult,
    RuntimeContextBundle,
    RuntimeExecutionOutcome,
    RuntimePlanningOutput,
    RuntimePlanningReport,
    RuntimePolicyOutcome,
    RuntimeTraceOutcome,
    RuntimeTurnPlan,
)
from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
from apeiria.conversation.models import ChatSessionIdentity


def test_reply_path_returns_committed_runtime_result() -> None:
    stages = _Stages()

    async def scenario() -> None:
        result = await _coordinator(stages).run(_request())

        assert result.outcome == "committed"
        assert result.reply_text == "hello from model"
        assert result.commit is not None
        assert result.diagnostics["path"] == "reply"
        assert result.diagnostics["selected_model"] == "source-1:profile-1:model-1"
        assert result.diagnostics["model_routing"] == _routing_diagnostics()
        planning_report = next(
            report for report in result.stage_reports if report.stage == "planning"
        )
        assert planning_report.diagnostics["model_routing"] == _routing_diagnostics()
        assert [report.stage for report in result.stage_reports] == [
            "policy",
            "observation",
            "context",
            "policy",
            "planning",
            "execution",
            "commit",
            "trace",
        ]
        assert stages.events == [
            "hard_policy",
            "deep_observation",
            "observation",
            "context",
            "social_policy",
            "planning",
            "execution",
            "commit",
            "trace",
        ]

    asyncio.run(scenario())


def test_reply_path_stops_on_hard_rule_skip() -> None:
    stages = _Stages(hard_should_reply=False)

    async def scenario() -> None:
        result = await _coordinator(stages).run(_request())

        assert result.outcome == "hard_rule_skipped"
        assert result.reply_text is None
        assert stages.events == [
            "hard_policy",
            "observed_turn",
            "trace",
        ]

    asyncio.run(scenario())


def test_reply_path_stops_on_social_no_reply() -> None:
    stages = _Stages(social_should_speak=False)

    async def scenario() -> None:
        result = await _coordinator(stages).run(_request())

        assert result.outcome == "social_no_reply"
        assert result.reply_text is None
        assert "execution" not in stages.events
        assert "commit" not in stages.events

    asyncio.run(scenario())


class _Stages:
    def __init__(
        self,
        *,
        hard_should_reply: bool = True,
        social_should_speak: bool = True,
    ) -> None:
        self.hard_should_reply = hard_should_reply
        self.social_should_speak = social_should_speak
        self.events: list[str] = []

    def evaluate(self, **_: Any) -> RuntimePolicyOutcome:
        self.events.append("hard_policy")
        return RuntimePolicyOutcome(
            stage="policy",
            source=_turn().source,
            decision=RuntimeHardRuleDecision(
                action="continue" if self.hard_should_reply else "observe",
                reason_codes=("direct_signal",),
                reason_text="test",
                evidence={},
                should_observe=True,
                should_reply=self.hard_should_reply,
            ),
        )

    async def decide_reply(self, **_: Any) -> ReplyStrategyDecision:
        self.events.append("social_policy")
        return ReplyStrategyDecision(
            action="reply" if self.social_should_speak else "silent",
            should_speak=self.social_should_speak,
            tool_mode="allow",
            reason_codes=("test",),
            reason_text="test",
            evidence={},
            decision_source="fallback",
        )

    async def apply(self, **_: Any) -> None:
        self.events.append("observation")

    async def apply_observed_turn(self, **_: Any) -> None:
        self.events.append("observed_turn")

    async def apply_deep_observation(self, **_: Any) -> None:
        self.events.append("deep_observation")

    async def assemble(self, **_: Any) -> RuntimeContextBundle:
        self.events.append("context")
        return RuntimeContextBundle(stage="context", context=_context())

    async def plan(self, **_: Any) -> RuntimePlanningOutput:
        self.events.append("planning")
        plan = RuntimeTurnPlan(
            stage="planning",
            selected=_selected_model(),
            fallback_models=(),
            tool_runtime=_tool_runtime(),
            skill_activation=None,
            pre_tool_task_class="reply_default",
            prompt_messages=(AIModelMessage(role="user", content="hello"),),
            tool_exposure_plan=ToolExposurePlan(),
        )
        return RuntimePlanningOutput(
            plan=plan,
            report=RuntimePlanningReport(
                selected_model_ref="source-1:profile-1:model-1",
                fallback_model_count=0,
                tool_exposure_summary={
                    "selected_tool_count": 0,
                    "has_executable_tools": False,
                },
                routing_diagnostics=_routing_diagnostics(),
            ),
        )

    async def execute(self, **_: Any) -> RuntimeExecutionOutcome:
        self.events.append("execution")
        return RuntimeExecutionOutcome(
            stage="execution",
            response=AIModelGenerateResponse(
                source_id="source-1",
                model_name="model-1",
                content="hello from model",
            ),
            tool_runtime=_tool_runtime(),
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=AgentTurnResult(
                trace_id="trace-1",
                runtime_mode="message",
                status="completed",
                finish_reason="completed",
                response=AIModelGenerateResponse(
                    source_id="source-1",
                    model_name="model-1",
                    content="hello from model",
                ),
            ),
        )

    async def commit(self, **_: Any) -> RuntimeCommitResult:
        self.events.append("commit")
        return RuntimeCommitResult(
            stage="commit",
            reply_text="hello from model",
            delivery_result=None,
            commit_status="committed",
        )

    def project(self, **_: Any) -> RuntimeTraceOutcome:
        from apeiria.app.ai.runtime.stages import RuntimeTraceOutcome
        from apeiria.app.ai.runtime.trace import TurnTrace

        self.events.append("trace")
        return RuntimeTraceOutcome(
            stage="trace",
            trace=TurnTrace(
                trace_id="trace-1",
                session_id="session-1",
                runtime_mode="message",
                strategy_action="continue",
                strategy_reason_codes=("direct_signal",),
            ),
        )


def _coordinator(stages: _Stages) -> AIRuntimeCoordinator:
    return AIRuntimeCoordinator(
        paths={
            "reply": ReplyPath(
                policy_stage=stages,
                observation_stage=stages,
                context_stage=stages,
                planning_stage=stages,
                execution_stage=stages,
                commit_stage=stages,
                trace_stage=stages,
            )
        }
    )


def _request() -> ReplyRuntimeRequest:
    return ReplyRuntimeRequest(
        trace_id="trace-1",
        trace=RuntimeTraceContext(kind="conversation", trigger="test"),
        turn=_turn(),
        current_time=datetime(2026, 5, 21, tzinfo=timezone.utc),
        wake_context=WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="hello",
            is_tome=True,
            is_private=True,
            is_future_task=False,
        ),
    )


def _turn() -> RuntimeTurnInput:
    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )
    return RuntimeTurnInput(
        identity=identity,
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="message-1",
            user_id="user-1",
            direct_signal=True,
            is_private=True,
        ),
        sender_id="bot-1",
    )


def _context() -> RuntimeContextMaterials:
    return RuntimeContextMaterials(
        turns=[],
        conversation_summary=None,
        relationship_target=AIRelationshipTarget(
            platform="test",
            scene_id="user-1",
            user_id="user-1",
            is_private=True,
        ),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        profile_card=(),
        profile_card_source_refs=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )


def _selected_model() -> AISelectedModel:
    return AISelectedModel(
        source=AISourceDefinition(
            source_id="source-1",
            name="Source",
            capability_type="chat_completion",
            client_type="openai",
            preset_type="openai_compatible",
            api_base=None,
            enabled=True,
            adapter_kind="openai_compatible",
        ),
        profile=AIModelProfileDefinition(
            profile_id="profile-1",
            name="profile",
            model_id="model-1",
            task_class="reply_default",
            priority=10,
            enabled=True,
        ),
        resolved_model_name="model-1",
        source_model=AIChatModelDefinition(
            model_id="model-1",
            source_id="source-1",
            model_identifier="model-1",
            display_name="Model",
            enabled=True,
        ),
    )


def _tool_runtime() -> RuntimeToolLoopResult:
    return RuntimeToolLoopResult(
        policy_text="",
        result_lines=(),
        turns=(),
    )


def _routing_diagnostics() -> dict[str, object]:
    return {
        "source": "route",
        "route_id": "route-1",
        "selected_profile_id": "profile-1",
        "selected_model": "source-1:profile-1:model-1",
        "fallback_model_count": 0,
    }
