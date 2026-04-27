from __future__ import annotations

from apeiria.ai.prompting import PromptPacket, PromptSection, render_flat
from apeiria.app.ai.session_read.prompt_preview import _to_prompt_channel_preview


def test_prompt_preview_exposes_packet_sections_and_rendered_output() -> None:
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

    preview = _to_prompt_channel_preview(packet, mode="planner")

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
