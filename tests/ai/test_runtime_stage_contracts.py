from __future__ import annotations

import inspect
from dataclasses import fields
from datetime import datetime
from typing import Any, get_args, get_type_hints

from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.runtime.commit import RuntimeCommitEffectsStage
from apeiria.app.ai.runtime.commit.delivery import DeliveryOutcome
from apeiria.app.ai.runtime.context.stage import RuntimeContextAssemblyStage
from apeiria.app.ai.runtime.execution.stage import RuntimeTurnExecutionStage
from apeiria.app.ai.runtime.live import DefaultAILiveRuntimeEntry
from apeiria.app.ai.runtime.observation import RuntimeObservationEffectsStage
from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
from apeiria.app.ai.runtime.planning.stage import RuntimeTurnPlanningStage
from apeiria.app.ai.runtime.policy import RuntimePolicyDecisionStage
from apeiria.app.ai.runtime.session.context import (
    RuntimeContextMaterials,
    RuntimeTurnInput,
    TurnContext,
)
from apeiria.app.ai.runtime.stages import (
    RuntimeCommitInput,
    RuntimeCommitStage,
    RuntimeContextStage,
    RuntimeExecutionOutcome,
    RuntimeExecutionStage,
    RuntimeIngressInput,
    RuntimeObservationStage,
    RuntimePlanningInput,
    RuntimePlanningStage,
    RuntimePolicyStage,
    RuntimeSocialDecisionInput,
    RuntimeTraceInput,
    RuntimeTraceStage,
    RuntimeTurnPlan,
)
from apeiria.app.ai.runtime.trace import RuntimeTraceProjectionStage

_STAGE_TYPE_GLOBALS = {
    "AgentTurnResult": AgentTurnResult,
    "datetime": datetime,
    "DeliveryOutcome": DeliveryOutcome,
    "ReplyStrategyDecision": ReplyStrategyDecision,
    "RuntimeTurnPlan": RuntimeTurnPlan,
    "RuntimeExecutionOutcome": RuntimeExecutionOutcome,
    "TurnContext": TurnContext,
    "WakeContext": WakeContext,
}


def _runtime_stage_type_hints(target: object) -> dict[str, object]:
    globalns = getattr(target, "__globals__", None)
    if globalns is None:
        module = __import__(target.__module__, fromlist=["__dict__"])
        globalns = module.__dict__
    return get_type_hints(
        target,
        globalns={
            **globalns,
            **_STAGE_TYPE_GLOBALS,
        },
    )


def test_turn_engine_declares_explicit_stage_contract_fields() -> None:
    field_names = {field.name for field in fields(AISessionTurnEngine)}

    assert {
        "policy_stage",
        "observation_stage",
        "context_stage",
        "planning_stage",
        "execution_stage",
        "commit_stage",
        "trace_stage",
    } <= field_names
    assert not any(
        "Callable" in str(annotation)
        for annotation in AISessionTurnEngine.__annotations__.values()
    )


def test_production_turn_engine_uses_native_stage_objects() -> None:
    engine = DefaultAILiveRuntimeEntry()._resolve_turn_engine()

    assert isinstance(engine.policy_stage, RuntimePolicyStage)
    assert isinstance(engine.observation_stage, RuntimeObservationStage)
    assert isinstance(engine.context_stage, RuntimeContextStage)
    assert isinstance(engine.planning_stage, RuntimePlanningStage)
    assert isinstance(engine.execution_stage, RuntimeExecutionStage)
    assert isinstance(engine.commit_stage, RuntimeCommitStage)
    assert isinstance(engine.trace_stage, RuntimeTraceStage)
    assert not hasattr(engine, "gather_reply_inputs")
    assert not hasattr(engine, "generate_reply")


def test_planning_stage_accepts_one_runtime_planning_input() -> None:
    planning_signature = inspect.signature(RuntimePlanningStage.plan)
    annotations = _runtime_stage_type_hints(RuntimePlanningStage.plan)

    assert tuple(planning_signature.parameters) == ("self", "planning_input")
    assert annotations["planning_input"] is RuntimePlanningInput


def test_runtime_planning_input_is_owned_by_stage_contracts() -> None:
    assert RuntimePlanningInput.__module__ == "apeiria.app.ai.runtime.stages"


def test_runtime_stage_inputs_use_runtime_owned_records() -> None:
    annotations = {
        cls.__name__: _runtime_stage_type_hints(cls)
        for cls in (
            RuntimeIngressInput,
            RuntimePlanningInput,
            RuntimeSocialDecisionInput,
            RuntimeCommitInput,
            RuntimeTraceInput,
        )
    }

    assert annotations["RuntimeIngressInput"]["turn"] is RuntimeTurnInput
    assert "request" not in annotations["RuntimeIngressInput"]
    assert annotations["RuntimePlanningInput"]["turn"] is RuntimeTurnInput
    assert annotations["RuntimePlanningInput"]["context"] is RuntimeContextMaterials
    assert "request" not in annotations["RuntimePlanningInput"]
    assert "inputs" not in annotations["RuntimePlanningInput"]
    assert annotations["RuntimeSocialDecisionInput"]["turn"] is RuntimeTurnInput
    assert annotations["RuntimeCommitInput"]["turn"] is RuntimeTurnInput
    assert annotations["RuntimeCommitInput"]["context"] is RuntimeContextMaterials
    assert annotations["RuntimeTraceInput"]["turn"] is RuntimeTurnInput


def test_ingress_stages_accept_one_runtime_ingress_input() -> None:
    for stage, method_name in (
        (RuntimePolicyStage, "evaluate"),
        (RuntimeObservationStage, "apply"),
        (RuntimeContextStage, "assemble"),
    ):
        signature = inspect.signature(getattr(stage, method_name))
        annotations = _runtime_stage_type_hints(getattr(stage, method_name))

        assert tuple(signature.parameters) == ("self", "ingress_input")
        assert annotations["ingress_input"] is RuntimeIngressInput


def test_runtime_ingress_input_is_owned_by_stage_contracts() -> None:
    assert RuntimeIngressInput.__module__ == "apeiria.app.ai.runtime.stages"


def test_social_policy_stage_accepts_one_runtime_social_input() -> None:
    signature = inspect.signature(RuntimePolicyStage.decide_reply)
    annotations = _runtime_stage_type_hints(RuntimePolicyStage.decide_reply)

    assert tuple(signature.parameters) == ("self", "social_input")
    assert annotations["social_input"] is RuntimeSocialDecisionInput


def test_runtime_social_decision_input_is_owned_by_stage_contracts() -> None:
    assert RuntimeSocialDecisionInput.__module__ == "apeiria.app.ai.runtime.stages"


def test_execution_helpers_accept_frozen_turn_context() -> None:
    for target in (
        RuntimeExecutionStage.execute,
        RuntimeTurnExecutionStage.execute,
        AISessionTurnEngine.execute_turn,
    ):
        signature = inspect.signature(target)
        annotations = _runtime_stage_type_hints(target)

        assert "turn_context" in signature.parameters
        assert annotations["turn_context"] is TurnContext


def test_commit_and_trace_stages_accept_one_runtime_input() -> None:
    for stage, method_name, parameter_name, expected_input in (
        (RuntimeCommitStage, "commit", "commit_input", RuntimeCommitInput),
        (RuntimeTraceStage, "project", "trace_input", RuntimeTraceInput),
    ):
        signature = inspect.signature(getattr(stage, method_name))
        annotations = _runtime_stage_type_hints(getattr(stage, method_name))

        assert tuple(signature.parameters) == ("self", parameter_name)
        assert annotations[parameter_name] is expected_input


def test_runtime_commit_and_trace_inputs_are_owned_by_stage_contracts() -> None:
    assert RuntimeCommitInput.__module__ == "apeiria.app.ai.runtime.stages"
    assert RuntimeTraceInput.__module__ == "apeiria.app.ai.runtime.stages"


def test_default_stage_dependencies_are_named_contracts() -> None:
    for stage_cls in (
        RuntimePolicyDecisionStage,
        RuntimeObservationEffectsStage,
        RuntimeContextAssemblyStage,
        RuntimeTurnPlanningStage,
        RuntimeCommitEffectsStage,
        RuntimeTraceProjectionStage,
    ):
        annotations = _runtime_stage_type_hints(stage_cls)
        for name, annotation in annotations.items():
            assert not _contains_any(annotation), (
                f"{stage_cls.__name__}.{name} exposes broad Any"
            )
            assert "Callable" not in str(annotation), (
                f"{stage_cls.__name__}.{name} exposes a loose Callable"
            )


def _contains_any(annotation: object) -> bool:
    if annotation is Any:
        return True
    return any(_contains_any(arg) for arg in get_args(annotation))
