from __future__ import annotations

import importlib
from pathlib import Path


def test_memory_steps_delegate_model_extraction() -> None:
    project_root = Path(__file__).resolve().parents[2]
    memory_steps_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "memory_steps.py"
    ).read_text(encoding="utf-8")

    extraction_module = importlib.import_module(
        "apeiria.app.ai.pipeline.memory_extraction_steps"
    )

    assert hasattr(extraction_module, "extract_memory_from_message")
    assert "model_gateway" not in memory_steps_source
    assert "AIModelRouteQuery" not in memory_steps_source
    assert "build_memory_extraction_prompt" not in memory_steps_source
    assert "parse_memory_extraction_response" not in memory_steps_source


def test_memory_steps_delegate_person_profile_loading() -> None:
    project_root = Path(__file__).resolve().parents[2]
    memory_steps_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "memory_steps.py"
    ).read_text(encoding="utf-8")

    person_profile_module = importlib.import_module(
        "apeiria.app.ai.pipeline.person_profile_steps"
    )

    assert hasattr(person_profile_module, "load_person_profile_for_prompt")
    assert "ai_person_profile_service" not in memory_steps_source
    assert "build_prompt_profile" not in memory_steps_source
