from __future__ import annotations

import importlib
import sys

import pytest


def test_import_app_ai_pipeline_exposes_public_surface() -> None:
    for module_name in (
        "apeiria.app.ai.pipeline",
        "apeiria.app.ai.pipeline.service",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.ai.pipeline")

    assert module.__name__ == "apeiria.app.ai.pipeline"
    assert module.__all__ == [
        "AIRuntimeComposeInput",
        "AIRuntimeService",
        "AITraceContext",
        "ai_runtime_service",
        "build_relationship_target",
        "compose_pre_tool_reply_prompt",
        "compose_reply_prompt",
        "compose_roleplay_reply_prompt",
        "load_relationship_context",
        "recall_memories",
        "store_extracted_memories",
        "update_relationship_state",
    ]
    assert "apeiria.app.ai.pipeline.service" not in sys.modules

    ai_runtime_service = module.ai_runtime_service

    assert (
        ai_runtime_service
        is sys.modules["apeiria.app.ai.pipeline.service"].ai_runtime_service
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.pipeline",
        "apeiria.ai.pipeline.composer",
        "apeiria.ai.pipeline.service",
    ],
)
def test_legacy_ai_pipeline_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
