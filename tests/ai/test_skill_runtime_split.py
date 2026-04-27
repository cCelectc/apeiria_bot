from __future__ import annotations

import importlib
from pathlib import Path


def test_skill_runtime_delegates_model_selection() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime_source = (
        project_root / "apeiria" / "ai" / "skills" / "runtime.py"
    ).read_text(encoding="utf-8")

    selection_module = importlib.import_module("apeiria.ai.skills.selection")

    assert hasattr(selection_module, "AISkillSelector")
    assert "model_gateway" not in runtime_source
    assert "AIModelRouteQuery" not in runtime_source
    assert "_build_skill_selection_prompt" not in runtime_source
    assert "_parse_skill_selection_response" not in runtime_source
