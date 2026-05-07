from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest  # noqa: TC002

import apeiria.app.ai.runtime.execution.stage as execution_stage_module
import apeiria.app.ai.runtime.live as service_module
from apeiria.ai.config import AIPluginConfig
from apeiria.ai.model import AIModelMessage
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.runtime.commit import RuntimeCommitEffectsStage
from apeiria.app.ai.runtime.context.stage import RuntimeContextAssemblyStage
from apeiria.app.ai.runtime.execution.stage import RuntimeTurnExecutionStage
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
from apeiria.app.ai.runtime.live import DefaultAILiveRuntimeEntry
from apeiria.app.ai.runtime.observation import RuntimeObservationEffectsStage
from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
from apeiria.app.ai.runtime.planning.stage import RuntimeTurnPlanningStage
from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
from apeiria.app.ai.runtime.policy import RuntimePolicyDecisionStage
from apeiria.app.ai.runtime.stages import (
    RuntimeContextMaterials,
    RuntimeExecutionOutcome,
    RuntimePlanningInput,
    RuntimeTurnPlan,
)
from apeiria.app.ai.runtime.trace import RuntimeTraceProjectionStage
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import model_response, selected_model


class _FakeChatSessionService:
    def __init__(self) -> None:
        self.calls = 0
        self.identity = ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type="group",
            scene_id="scene-1",
            subject_id="user-1",
        )

    async def ingest_event(self, *_args: Any, **_kwargs: Any) -> object:
        self.calls += 1
        return self.identity, SimpleNamespace(
            message_id=f"local-msg-{self.calls}",
            platform_message_id="platform-msg-1",
        )


async def _noop_observation_effects(*_args: Any, **_kwargs: Any) -> None:
    return None


def _empty_tool_result() -> RuntimeToolLoopResult:
    return RuntimeToolLoopResult(policy_text="", result_lines=(), turns=())


def test_duplicate_platform_event_stops_before_ai_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    counts = {
        "memory": 0,
        "inputs": 0,
        "social": 0,
        "model": 0,
        "assistant": 0,
    }
    chat_service = _FakeChatSessionService()

    monkeypatch.setattr(
        service_module,
        "ensure_ai_runtime_support_initialized",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(service_module, "get_ai_plugin_config", AIPluginConfig)
    monkeypatch.setattr(
        service_module,
        "build_wake_context",
        lambda *_args, **_kwargs: WakeContext(
            bot_self_id="bot-1",
            user_id="user-1",
            message_text="hello",
            is_tome=True,
            is_private=False,
            is_future_task=False,
            allow_group_initiative=True,
        ),
    )
    monkeypatch.setattr(
        service_module,
        "evaluate_wake",
        lambda _wake_context: SimpleNamespace(should_process=True),
    )
    monkeypatch.setattr(
        service_module,
        "ai_retention_service",
        SimpleNamespace(maybe_schedule_cleanup=lambda **_kwargs: None),
    )
    monkeypatch.setattr(service_module, "chat_session_service", chat_service)

    async def store_extracted_memories(*_args: Any, **_kwargs: Any) -> object:
        counts["memory"] += 1
        return SimpleNamespace(sentiment=object())

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> object:
        counts["inputs"] += 1
        return RuntimeContextMaterials(
            turns=[],
            conversation_summary=None,
            relationship_target=object(),  # type: ignore[arg-type]
            relationship_context=None,
            persona=None,
            allowed_tools=(),
            initiative_bias=0.0,
            model_target=object(),
            tool_policy=AIToolPolicy(),
            recalled_memories=[],
            person_profile=(),
        )

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        counts["social"] += 1
        return ReplyStrategyDecision(
            action="reply",
            should_speak=True,
            tool_mode="avoid",
            reason_codes=("direct",),
            reason_text="direct",
            evidence={},
            decision_source="llm",
        )

    async def prepare_generation(
        *,
        planning_input: RuntimePlanningInput,
    ) -> RuntimeTurnPlan:
        assert planning_input.context is not None
        return RuntimeTurnPlan(
            stage="planning",
            selected=selected_model("duplicate"),
            fallback_models=(),
            skill_runtime=_empty_tool_result(),
            skill_activation=None,
            pre_tool_task_class="reply_default",
            prompt_messages=(AIModelMessage(role="user", content="hello"),),
            prompt_diagnostics={},
            tool_exposure_plan=ToolExposurePlan(),
        )

    async def execute_runtime_turn(
        *_args: Any,
        **_kwargs: Any,
    ) -> RuntimeExecutionOutcome:
        counts["model"] += 1
        selected = selected_model("duplicate")
        return RuntimeExecutionOutcome(
            stage="execution",
            response=model_response(selected, "reply"),
            skill_runtime=_empty_tool_result(),
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=None,
        )

    class ReplyPersistenceStage:
        async def persist_tool_observations(self, **_: object) -> str:
            return "not_required"

        async def persist_assistant_message(self, **_: object) -> None:
            counts["assistant"] += 1

        async def rebuild_context_window(self, **_: object) -> None:
            return None

    monkeypatch.setattr(
        service_module,
        "store_extracted_memories",
        store_extracted_memories,
    )
    monkeypatch.setattr(
        execution_stage_module,
        "execute_runtime_turn",
        execute_runtime_turn,
    )
    service = DefaultAILiveRuntimeEntry(
        turn_engine=AISessionTurnEngine(
            policy_stage=RuntimePolicyDecisionStage(decide_whether_to_speak),
            observation_stage=RuntimeObservationEffectsStage(
                _noop_observation_effects,
            ),
            context_stage=RuntimeContextAssemblyStage(gather_reply_inputs),
            planning_stage=RuntimeTurnPlanningStage(prepare_generation),
            execution_stage=RuntimeTurnExecutionStage(),
            commit_stage=RuntimeCommitEffectsStage(
                reply_persistence=ReplyPersistenceStage(),
                reply_strategy_service=SimpleNamespace(
                    notify_replied=lambda _session_id: None
                ),
            ),
            trace_stage=RuntimeTraceProjectionStage(),
        )
    )

    bot = SimpleNamespace(self_id="bot-1")
    event = SimpleNamespace(get_user_id=lambda: "user-1", is_tome=lambda: True)

    first = asyncio.run(service.handle_message(bot, event))  # type: ignore[arg-type]
    duplicate = asyncio.run(service.handle_message(bot, event))  # type: ignore[arg-type]

    assert first == "reply"
    assert duplicate is None
    expected_ingest_calls = 2
    assert chat_service.calls == expected_ingest_calls
    assert counts == {
        "memory": 1,
        "inputs": 1,
        "social": 1,
        "model": 1,
        "assistant": 1,
    }
