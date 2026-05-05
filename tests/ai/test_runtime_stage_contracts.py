from __future__ import annotations

import inspect
from dataclasses import fields
from typing import get_type_hints

from apeiria.app.ai.pipeline.service import AIRuntimeService
from apeiria.app.ai.session_runtime import (
    RuntimeCommitStage,
    RuntimeContextStage,
    RuntimeExecutionStage,
    RuntimeObservationStage,
    RuntimePlanningInput,
    RuntimePlanningStage,
    RuntimePolicyStage,
    RuntimeTraceStage,
)
from apeiria.app.ai.session_runtime.engine import AISessionTurnEngine


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
    engine = AIRuntimeService()._resolve_turn_engine()

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
    annotations = get_type_hints(RuntimePlanningStage.plan)

    assert tuple(planning_signature.parameters) == ("self", "planning_input")
    assert annotations["planning_input"] is RuntimePlanningInput


def test_runtime_planning_input_is_owned_by_stage_contracts() -> None:
    assert RuntimePlanningInput.__module__ == "apeiria.app.ai.session_runtime.stages"
