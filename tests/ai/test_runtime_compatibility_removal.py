from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

from apeiria.app.ai.runtime.execution.stage import RuntimeTurnExecutionStage
from apeiria.app.ai.runtime.live import DefaultAILiveRuntimeEntry
from apeiria.app.ai.runtime.stages import RuntimeExecutionStage


def test_execution_stage_contract_uses_native_context_and_plan_only() -> None:
    signature = inspect.signature(RuntimeExecutionStage.execute)

    assert tuple(signature.parameters) == ("self", "turn_context", "plan")


def test_default_execution_stage_does_not_wrap_legacy_generation_callable() -> None:
    signature = inspect.signature(RuntimeTurnExecutionStage)

    assert "generate_reply" not in signature.parameters
    assert fields(RuntimeTurnExecutionStage) == ()


def test_production_runtime_uses_native_execution_stage() -> None:
    engine = DefaultAILiveRuntimeEntry()._resolve_turn_engine()

    assert isinstance(engine.execution_stage, RuntimeTurnExecutionStage)
    assert not hasattr(engine.execution_stage, "generate_reply")


def test_pipeline_generation_no_longer_owns_live_reply_execution() -> None:
    assert not Path("apeiria/app/ai/pipeline/generation_steps.py").exists()


def test_runtime_execution_owns_direct_and_tool_capable_paths() -> None:
    execution_source = Path("apeiria/app/ai/runtime/execution/__init__.py").read_text()

    assert "execute_direct_runtime_turn" in execution_source
    assert "execute_tool_capable_runtime_turn" in execution_source
    assert "apeiria.app.ai.pipeline.composer" not in execution_source
    assert "apeiria.app.ai.pipeline.model_steps" not in execution_source
    assert "apeiria.app.ai.pipeline.routing" not in execution_source


def test_runtime_commit_owns_post_execution_side_effects() -> None:
    commit_source = Path("apeiria/app/ai/runtime/commit/__init__.py").read_text()
    engine_source = Path("apeiria/app/ai/runtime/orchestrator.py").read_text()

    for expected in (
        "RuntimeCommitEffectsStage",
        "persist_tool_observations",
        "persist_assistant_message",
        "rebuild_context_window",
        "record_ambient_reply",
        "deliver_reply",
    ):
        assert expected in commit_source

    for stale in (
        "_commit_delivery",
        "_commit_required_persistence",
        "_commit_context_window",
        "_commit_reply_accounting",
    ):
        assert stale not in engine_source


def test_runtime_trace_owns_projection_and_persistence() -> None:
    trace_source = Path("apeiria/app/ai/runtime/trace/__init__.py").read_text()
    engine_source = Path("apeiria/app/ai/runtime/orchestrator.py").read_text()

    for expected in (
        "TurnTrace",
        "project_turn_trace",
        "RuntimeTraceProjectionStage",
        "TurnTraceRepository",
        "store_trace",
    ):
        assert expected in trace_source

    assert "class RuntimeTraceProjectionStage" not in engine_source


def test_runtime_and_read_surfaces_do_not_expose_tool_loading_compat_wrapper() -> None:
    for source_path in (
        Path("apeiria/app/ai/runtime/live.py"),
        Path("apeiria/app/ai/sessions/prompt_preview.py"),
        Path("apeiria/app/ai/tooling.py"),
    ):
        assert "ensure_app_ai_tools_loaded" not in source_path.read_text()


def test_admin_read_surfaces_use_native_trace_and_prompt_diagnostics() -> None:
    trace_source = Path("apeiria/app/ai/diagnostics/traces.py").read_text()
    prompt_preview_source = Path(
        "apeiria/app/ai/sessions/prompt_preview.py"
    ).read_text()
    prompt_projection_source = Path(
        "apeiria/app/ai/sessions/prompt_projection.py"
    ).read_text()

    assert "runtime.trace" in trace_source
    assert "generation_steps" not in trace_source
    assert "build_initial_reply_prompt_packet" in prompt_preview_source
    assert "project_prompt_packet_to_preview" in prompt_preview_source
    assert "prompt_region_diagnostics" in prompt_projection_source
    assert "generation_steps" not in prompt_preview_source
    assert "generation_steps" not in prompt_projection_source


def test_prompt_preview_does_not_rebuild_legacy_pipeline_inputs() -> None:
    prompt_preview_source = Path(
        "apeiria/app/ai/sessions/prompt_preview.py"
    ).read_text()

    assert "AIRuntimeTurnRequest" not in prompt_preview_source
    assert "RuntimeContextInputBundle" not in prompt_preview_source
    assert "type: ignore" not in prompt_preview_source


def test_runtime_stage_and_preview_contracts_do_not_expose_legacy_dtos() -> None:
    for source_path in (
        Path("apeiria/app/ai/runtime/stages.py"),
        Path("apeiria/app/ai/runtime/planning/turn.py"),
        Path("apeiria/app/ai/runtime/context/adapter.py"),
        Path("apeiria/app/ai/runtime/orchestrator.py"),
        Path("apeiria/app/ai/sessions/prompt_preview.py"),
    ):
        source = source_path.read_text()

        assert "AIRuntimeTurnRequest" not in source
        assert "RuntimeContextInputBundle" not in source


def test_live_runtime_does_not_call_legacy_social_skip_mapping() -> None:
    engine_source = Path("apeiria/app/ai/runtime/orchestrator.py").read_text()

    assert "map_legacy_skip_to_runtime_decision" not in engine_source
