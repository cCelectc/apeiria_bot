from __future__ import annotations

import importlib
from pathlib import Path

from apeiria.ai.prompting import PromptPacket, PromptSection, render_flat


def test_prompt_preview_exposes_packet_sections_and_rendered_output() -> None:
    module = importlib.import_module("apeiria.app.ai.session_read.prompt_projection")
    project_prompt_packet_to_channels = module.project_prompt_packet_to_channels

    packet = PromptPacket(
        purpose="reply_planner",
        sections=(
            PromptSection(
                role="system",
                name="SystemInstructions",
                content="Plan the reply.",
            ),
            PromptSection(role="system", name="Persona", content="Persona text."),
            PromptSection(role="system", name="ToolPolicy", content="Use tools."),
            PromptSection(role="user", name="Conversation", content="User: hello"),
            PromptSection(role="user", name="Instruction", content="Decide action."),
        ),
    )

    preview = project_prompt_packet_to_channels(packet, mode="planner")

    assert [section.name for section in preview.sections] == [
        "SystemInstructions",
        "Persona",
        "ToolPolicy",
        "Conversation",
        "Instruction",
    ]
    assert preview.tool_policy == "Use tools."
    assert preview.conversation_messages == ("User: hello",)
    assert render_flat(packet).endswith("[Instruction]\nDecide action.")


def test_prompt_preview_uses_central_packet_projection() -> None:
    project_root = Path(__file__).resolve().parents[2]
    preview_source = (
        project_root / "apeiria" / "app" / "ai" / "session_read" / "prompt_preview.py"
    ).read_text(encoding="utf-8")

    assert "project_prompt_packet_to_channels" in preview_source
    assert "_to_prompt_channel_preview" not in preview_source
    assert "def _section_text" not in preview_source
    assert "def _section_lines" not in preview_source
