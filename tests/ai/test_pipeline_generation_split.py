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
