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


def test_generation_steps_delegate_reply_input_gathering() -> None:
    project_root = Path(__file__).resolve().parents[2]
    generation_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py"
    ).read_text(encoding="utf-8")

    input_steps_module = importlib.import_module("apeiria.app.ai.pipeline.input_steps")

    assert hasattr(input_steps_module, "ReplyInputs")
    assert hasattr(input_steps_module, "gather_reply_inputs")
    assert "build_and_store_context_window" not in generation_source
    assert "recall_memories" not in generation_source
    assert "load_persona_bundle" not in generation_source
    assert "update_relationship_state" not in generation_source
    assert "ai_tool_service" not in generation_source


def test_generation_steps_use_prompt_packets_for_reply_generation() -> None:
    project_root = Path(__file__).resolve().parents[2]
    generation_source = (
        project_root / "apeiria" / "app" / "ai" / "pipeline" / "generation_steps.py"
    ).read_text(encoding="utf-8")

    assert "compose_pre_tool_reply_prompt" not in generation_source
    assert "compose_roleplay_reply_prompt" not in generation_source
    assert "build_chat_messages" not in generation_source
    assert "build_pre_tool_reply_messages" in generation_source
    assert "build_roleplay_reply_messages" in generation_source
    assert 'prompt=""' not in generation_source
