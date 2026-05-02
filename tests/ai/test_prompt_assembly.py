from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime, timezone

from apeiria.ai.memory import AIMemoryDefinition
from apeiria.ai.prompting import (
    PromptPacket,
    PromptRegionProjection,
    PromptSection,
    ReplyPromptInput,
    build_reply_final_packet,
    build_reply_planner_packet,
    project_prompt_regions,
    project_reply_prompt_regions,
    prompt_region_diagnostics,
    render_flat,
    render_messages,
)
from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class _Persona:
    persona_id: str = "persona-1"
    system_prompt: str = "You are Apeiria."
    style_prompt: str = "Speak softly."


def _turn(
    role: str,
    text: str,
    *,
    author_name: str | None = None,
) -> ChatContextMessageView:
    return ChatContextMessageView(
        message_id=f"msg-{role}",
        author_role=role,  # type: ignore[arg-type]
        author_id=f"{role}-1",
        author_name=author_name,
        text_content=text,
        content=None,
        created_at=datetime.now(timezone.utc),
    )


def _memory(layer: str, content: str) -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id=f"memory-{layer}",
        anchor_type="user",
        anchor_id="user-1",
        memory_layer=layer,  # type: ignore[arg-type]
        memory_kind="fact",
        content=content,
        is_editable=True,
        is_ignored=False,
        source_message_id=None,
        salience=0.8,
        confidence=0.7,
        last_recalled_at=None,
        created_at=datetime.now(timezone.utc),
    )


def _reply_input() -> ReplyPromptInput:
    return ReplyPromptInput(
        persona=_Persona(),
        scene_type="private",
        relationship="relationship context",
        tool_policy="allowed: memory.query",
        tool_results=("- [memory.query] result",),
        memories=(
            _memory("operator", "operator note"),
            _memory("long_term", "likes tea"),
        ),
        turns=(
            _turn("user", "hello", author_name="Alice"),
            _turn("assistant", "hi"),
        ),
        person_profile=("profile: Alice",),
        conversation_summary="summary text",
        social_policy_summary="social policy",
        future_task_context="task_id=task-1",
        skill_activation="use active skill",
    )


def test_prompt_renderer_preserves_order_and_omits_empty_sections() -> None:
    packet = PromptPacket(
        purpose="reply_final",
        sections=(
            PromptSection(role="system", name="Persona", content="persona"),
            PromptSection(role="system", name="Empty", content="  "),
            PromptSection(role="user", name="Conversation", content="User: hi"),
            PromptSection(role="user", name="Instruction", content="Reply now."),
        ),
    )

    messages = render_messages(packet)

    assert [message.role for message in messages] == ["system", "user"]
    assert "[Persona]\npersona" in messages[0].content
    assert "Empty" not in messages[0].content
    assert messages[1].content.split("\n\n") == [
        "[Conversation]\nUser: hi",
        "[Instruction]\nReply now.",
    ]
    assert render_flat(packet) == (
        "[Persona]\npersona\n\n[Conversation]\nUser: hi\n\n[Instruction]\nReply now."
    )


def test_prompting_public_exports_are_explicit() -> None:
    module = importlib.import_module("apeiria.ai.prompting")

    assert not hasattr(module, "__getattr__")
    assert module.__all__ == [
        "ConversationSummaryPromptInput",
        "MemoryExtractionPromptInput",
        "PromptPacket",
        "PromptPurpose",
        "PromptRegion",
        "PromptRegionProjection",
        "PromptSection",
        "PromptSectionRole",
        "ReplyPersonaPromptBundleLike",
        "ReplyPromptInput",
        "ReplyPromptMode",
        "SkillCatalogEntryLike",
        "SkillSelectionPromptInput",
        "SocialEngagementType",
        "SocialJudgmentPromptInput",
        "ToolIntentPlanningPromptInput",
        "build_conversation_summary_packet",
        "build_memory_extraction_packet",
        "build_reply_final_packet",
        "build_reply_planner_packet",
        "build_skill_selection_packet",
        "build_social_judgment_packet",
        "build_tool_intent_planning_packet",
        "project_prompt_regions",
        "project_reply_prompt_regions",
        "prompt_region_diagnostics",
        "render_flat",
        "render_messages",
    ]


def test_prompt_region_projection_is_inspectable_and_preserves_rendering() -> None:
    packet = PromptPacket(
        purpose="reply_final",
        sections=(
            PromptSection(role="system", name="SystemInstructions", content="runtime"),
            PromptSection(role="system", name="Persona", content="persona"),
            PromptSection(role="system", name="Memory", content="memory"),
            PromptSection(role="user", name="Instruction", content="reply"),
        ),
    )

    projection = project_prompt_regions(
        packet,
        stable_section_names=("SystemInstructions", "Persona"),
    )

    assert isinstance(projection, PromptRegionProjection)
    assert [section.name for section in projection.stable] == [
        "SystemInstructions",
        "Persona",
    ]
    assert [section.name for section in projection.dynamic] == [
        "Memory",
        "Instruction",
    ]
    assert render_messages(projection.to_packet()) == render_messages(packet)


def test_prompt_region_diagnostics_are_bounded() -> None:
    packet = PromptPacket(
        purpose="reply_final",
        sections=(
            PromptSection(role="system", name="SystemInstructions", content="runtime"),
            PromptSection(role="system", name="Persona", content="persona"),
            PromptSection(role="user", name="Instruction", content="reply"),
        ),
    )

    diagnostics = prompt_region_diagnostics(
        project_prompt_regions(
            packet,
            stable_section_names=("SystemInstructions", "Persona"),
        )
    )

    assert diagnostics == {
        "prompt_purpose": "reply_final",
        "stable_section_names": ("SystemInstructions", "Persona"),
        "dynamic_section_names": ("Instruction",),
        "stable_section_count": 2,
        "dynamic_section_count": 1,
        "total_section_count": 3,
    }
    assert "persona" not in str(diagnostics)


def test_reply_prompt_regions_keep_stable_prefix_before_dynamic_turn_data() -> None:
    packet = build_reply_planner_packet(_reply_input())

    projection = project_reply_prompt_regions(packet)
    stable_names = [section.name for section in projection.stable]
    dynamic_names = [section.name for section in projection.dynamic]

    assert stable_names == [
        "SystemInstructions",
        "Persona",
        "Style",
        "ResponseRules",
    ]
    assert "SocialPolicy" in dynamic_names
    assert "Relationship" in dynamic_names
    assert "ToolPolicy" in dynamic_names
    assert "ToolResults" in dynamic_names
    assert "LongTermMemories" in dynamic_names
    assert "Conversation" in dynamic_names
    assert dynamic_names[-1] == "Instruction"
    assert render_messages(projection.to_packet()) == render_messages(packet)


def test_capability_awareness_lives_in_stable_reply_region() -> None:
    inputs = ReplyPromptInput(
        persona=_Persona(),
        scene_type="private",
        relationship=None,
        tool_policy="allowed: memory.query",
        tool_results=(),
        memories=(),
        turns=(_turn("user", "hello"),),
        person_profile=(),
        capability_awareness="Capabilities may be selected when useful.",
    )

    packet = build_reply_planner_packet(inputs)
    projection = project_reply_prompt_regions(packet)
    names = [section.name for section in packet.sections]

    assert [section.name for section in projection.stable] == [
        "SystemInstructions",
        "Persona",
        "Style",
        "CapabilityAwareness",
        "ResponseRules",
    ]
    assert "CapabilityAwareness" not in [section.name for section in projection.dynamic]
    assert names.index("CapabilityAwareness") < names.index("ToolPolicy")


def test_reply_planner_recipe_sections_are_ordered_and_optional_sections_omit() -> None:
    packet = build_reply_planner_packet(_reply_input())

    names = [section.name for section in packet.sections]

    assert packet.purpose == "reply_planner"
    assert names[:4] == [
        "SystemInstructions",
        "Persona",
        "Style",
        "ResponseRules",
    ]
    assert "ToolPolicy" in names
    assert "ActiveSkills" in names
    assert names.index("ResponseRules") < names.index("Conversation")
    assert names[-1] == "Instruction"

    no_optional = build_reply_final_packet(
        ReplyPromptInput(
            persona=None,
            scene_type="private",
            relationship=None,
            tool_policy=None,
            tool_results=(),
            memories=(),
            turns=(),
            person_profile=(),
        )
    )
    no_optional_names = [section.name for section in no_optional.sections]

    assert no_optional.purpose == "reply_final"
    assert "ToolPolicy" not in no_optional_names
    assert "Relationship" not in no_optional_names
    assert "Conversation" in no_optional_names


def test_reply_final_recipe_includes_tool_results_without_tool_policy() -> None:
    packet = build_reply_final_packet(_reply_input())
    names = [section.name for section in packet.sections]

    assert "ToolResults" in names
    assert "ToolPolicy" not in names
    assert names.index("ToolResults") < names.index("Conversation")
