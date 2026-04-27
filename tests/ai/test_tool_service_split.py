from __future__ import annotations

import importlib
from pathlib import Path


def test_tool_service_delegates_execution_storage() -> None:
    project_root = Path(__file__).resolve().parents[2]
    service_source = (
        project_root / "apeiria" / "ai" / "tools" / "service.py"
    ).read_text(encoding="utf-8")

    contracts_module = importlib.import_module("apeiria.ai.tools.contracts")
    repository_module = importlib.import_module("apeiria.ai.tools.execution_repository")

    assert hasattr(contracts_module, "AIToolExecutionCreateInput")
    assert hasattr(repository_module, "AIToolExecutionRepository")
    assert "database_runtime" not in service_source
    assert "INSERT INTO ai_tool_execution" not in service_source
    assert "SELECT" not in service_source


def test_tool_service_delegates_model_intent_planning() -> None:
    project_root = Path(__file__).resolve().parents[2]
    service_source = (
        project_root / "apeiria" / "ai" / "tools" / "service.py"
    ).read_text(encoding="utf-8")

    planning_module = importlib.import_module("apeiria.ai.tools.planning")

    assert hasattr(planning_module, "AIToolIntentPlanner")
    assert "build_tool_planning_prompt" not in service_source
    assert "build_function_tools" not in service_source
    assert "build_intents_from_tool_calls" not in service_source
    assert "model_gateway" not in service_source
