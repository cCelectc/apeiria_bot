"""Production composition for the live AI runtime."""

from __future__ import annotations

from apeiria.ai.config import get_ai_plugin_config
from apeiria.app.ai.reply_strategy.service import reply_strategy_service
from apeiria.app.ai.runtime.commit import RuntimeCommitEffectsStage
from apeiria.app.ai.runtime.commit.delivery import deliver_generated_reply
from apeiria.app.ai.runtime.commit.persistence import AssistantReplyPersistenceStage
from apeiria.app.ai.runtime.context.context_window import record_context_usage
from apeiria.app.ai.runtime.context.materials import gather_reply_inputs
from apeiria.app.ai.runtime.context.observations import (
    apply_deep_memory_observation,
    apply_reply_observation_effects,
    persist_observed_conversation_turn,
)
from apeiria.app.ai.runtime.context.stage import RuntimeContextAssemblyStage
from apeiria.app.ai.runtime.execution.stage import RuntimeTurnExecutionStage
from apeiria.app.ai.runtime.observation import RuntimeObservationEffectsStage
from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
from apeiria.app.ai.runtime.planning.stage import RuntimeTurnPlanningStage
from apeiria.app.ai.runtime.planning.wake import decide_whether_to_speak
from apeiria.app.ai.runtime.policy import RuntimePolicyDecisionStage
from apeiria.app.ai.runtime.session.runtime import (
    InMemoryAISessionRuntimeResolver,
    SessionRuntimePolicy,
)
from apeiria.app.ai.runtime.trace import (
    RuntimeTraceProjectionStage,
    turn_trace_repository,
)


def create_session_runtime_resolver() -> InMemoryAISessionRuntimeResolver:
    """Build the default process-local session runtime resolver."""

    return InMemoryAISessionRuntimeResolver(
        policy=SessionRuntimePolicy.from_config(get_ai_plugin_config())
    )


def create_session_turn_engine() -> AISessionTurnEngine:
    """Build the default turn engine and production runtime stages."""

    return AISessionTurnEngine(
        policy_stage=RuntimePolicyDecisionStage(
            reply_decider=decide_whether_to_speak,
        ),
        observation_stage=RuntimeObservationEffectsStage(
            apply_observation_effects=apply_reply_observation_effects,
            persist_observed_turn=persist_observed_conversation_turn,
            apply_deep_observation_effects=apply_deep_memory_observation,
        ),
        context_stage=RuntimeContextAssemblyStage(
            gather_reply_inputs=gather_reply_inputs,
        ),
        planning_stage=RuntimeTurnPlanningStage(),
        execution_stage=RuntimeTurnExecutionStage(),
        commit_stage=RuntimeCommitEffectsStage(
            reply_persistence=AssistantReplyPersistenceStage(),
            reply_strategy_service=reply_strategy_service,
            deliver_reply=deliver_generated_reply,
            record_context_usage=record_context_usage,
        ),
        trace_stage=RuntimeTraceProjectionStage(trace_store=turn_trace_repository),
    )


__all__ = ["create_session_runtime_resolver", "create_session_turn_engine"]
