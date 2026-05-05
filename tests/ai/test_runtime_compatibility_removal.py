from __future__ import annotations

import inspect
from dataclasses import fields
from pathlib import Path

from apeiria.app.ai.pipeline.service import AIRuntimeService
from apeiria.app.ai.session_runtime import RuntimeExecutionStage
from apeiria.app.ai.session_runtime.engine import DefaultRuntimeExecutionStage


def test_execution_stage_contract_uses_native_context_and_plan_only() -> None:
    signature = inspect.signature(RuntimeExecutionStage.execute)

    assert tuple(signature.parameters) == ("self", "turn_context", "plan")


def test_default_execution_stage_does_not_wrap_legacy_generation_callable() -> None:
    signature = inspect.signature(DefaultRuntimeExecutionStage)

    assert "generate_reply" not in signature.parameters
    assert fields(DefaultRuntimeExecutionStage) == ()


def test_production_runtime_uses_native_execution_stage() -> None:
    engine = AIRuntimeService()._resolve_turn_engine()

    assert isinstance(engine.execution_stage, DefaultRuntimeExecutionStage)
    assert not hasattr(engine.execution_stage, "generate_reply")


def test_pipeline_generation_no_longer_owns_live_reply_execution() -> None:
    assert not Path("apeiria/app/ai/pipeline/generation_steps.py").exists()


def test_runtime_and_read_surfaces_do_not_expose_tool_loading_compat_wrapper() -> None:
    for source_path in (
        Path("apeiria/app/ai/pipeline/service.py"),
        Path("apeiria/app/ai/session_read/prompt_preview.py"),
        Path("apeiria/app/ai/tooling.py"),
    ):
        assert "ensure_app_ai_tools_loaded" not in source_path.read_text()


def test_admin_read_surfaces_use_native_trace_and_prompt_diagnostics() -> None:
    trace_source = Path("apeiria/app/ai/admin/traces.py").read_text()
    prompt_preview_source = Path(
        "apeiria/app/ai/session_read/prompt_preview.py"
    ).read_text()
    prompt_projection_source = Path(
        "apeiria/app/ai/session_read/prompt_projection.py"
    ).read_text()

    assert "session_runtime.trace_store" in trace_source
    assert "generation_steps" not in trace_source
    assert "build_initial_runtime_reply_prompt_packet" in prompt_preview_source
    assert "project_prompt_packet_to_preview" in prompt_preview_source
    assert "prompt_region_diagnostics" in prompt_projection_source
    assert "generation_steps" not in prompt_preview_source
    assert "generation_steps" not in prompt_projection_source
