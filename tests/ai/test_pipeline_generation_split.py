from __future__ import annotations

import importlib
from pathlib import Path


def test_generation_steps_delegate_reply_delivery() -> None:
    project_root = Path(__file__).resolve().parents[2]
    generation_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py"
    ).read_text(encoding="utf-8")

    delivery_module = importlib.import_module("apeiria.app.ai.pipeline.delivery_steps")

    assert hasattr(delivery_module, "DeliveryOutcome")
    assert hasattr(delivery_module, "deliver_generated_reply")
    assert "_deliver_generated_reply" not in generation_source
    assert "nonebot.get_bots" not in generation_source
    assert "send_group_msg" not in generation_source
    assert "send_private_msg" not in generation_source


def test_generation_steps_delegate_model_io() -> None:
    project_root = Path(__file__).resolve().parents[2]
    generation_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py"
    ).read_text(encoding="utf-8")

    model_steps_module = importlib.import_module("apeiria.app.ai.pipeline.model_steps")

    assert hasattr(model_steps_module, "GenerationRequest")
    assert hasattr(model_steps_module, "select_pipeline_model")
    assert hasattr(model_steps_module, "safe_generate_model")
    assert "model_gateway" not in generation_source
    assert "AIModelRouteQuery" not in generation_source
    assert "generate_native" not in generation_source
