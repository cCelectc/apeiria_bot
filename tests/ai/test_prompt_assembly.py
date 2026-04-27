from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apeiria.ai.memory import AIMemoryDefinition
from apeiria.ai.prompting import (
    PromptPacket,
    PromptSection,
    ReplyPromptInput,
    build_reply_final_packet,
    build_reply_planner_packet,
    render_flat,
    render_messages,
)
from apeiria.conversation.models import ChatContextMessageView

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTING_ROOT = REPO_ROOT / "apeiria" / "ai" / "prompting"


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
        "render_flat",
        "render_messages",
    ]


def test_reply_planner_recipe_sections_are_ordered_and_optional_sections_omit() -> None:
    packet = build_reply_planner_packet(_reply_input())

    names = [section.name for section in packet.sections]

    assert packet.purpose == "reply_planner"
    assert names[:4] == [
        "SystemInstructions",
        "Persona",
        "Style",
        "Relationship",
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


def test_prompt_renderers_do_not_import_business_modules() -> None:
    tree = ast.parse((PROMPTING_ROOT / "renderer.py").read_text(encoding="utf-8"))
    forbidden = (
        "apeiria.app.ai.pipeline",
        "apeiria.ai.persona",
        "apeiria.ai.memory",
        "apeiria.ai.relationship",
        "apeiria.ai.tools",
        "apeiria.ai.skills",
    )
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(forbidden):
                violations.append(module)
        elif isinstance(node, ast.Import):
            violations.extend(
                alias.name for alias in node.names if alias.name.startswith(forbidden)
            )

    assert not violations


def test_reply_recipes_do_not_cross_runtime_or_persistence_boundaries() -> None:
    source = (PROMPTING_ROOT / "reply.py").read_text(encoding="utf-8")

    for forbidden in (
        "select_pipeline_model",
        "generate_model_turn",
        "model_gateway",
        "tool_gateway",
        "deliver_generated_reply",
        "append_tool_observation_turns",
        "chat_session_service",
        "repository",
    ):
        assert forbidden not in source


def test_pipeline_does_not_own_reply_prompt_sections() -> None:
    pipeline_root = REPO_ROOT / "apeiria" / "app" / "ai" / "pipeline"

    assert not (pipeline_root / "prompting.py").exists()
    assert not (pipeline_root / "message_builder.py").exists()
    for path in pipeline_root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "PromptSection(" not in source
        assert "AIReplyPromptChannels" not in source
