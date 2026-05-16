from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from apeiria.ai.knowledge.models import KnowledgeRetrievalItem
from apeiria.ai.memory.models import AIMemoryDefinition
from apeiria.ai.prompting import (
    ConversationSummaryPromptInput,
    build_conversation_summary_packet,
    render_flat,
    render_messages,
)
from apeiria.ai.prompting.models import PromptPacket, PromptSection
from apeiria.ai.prompting.reply import (
    ReplyPromptInput,
    build_reply_final_packet,
    build_reply_planner_packet,
    project_reply_prompt_regions,
)
from apeiria.ai.prompting.template_loader import load_prompt_template
from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class _Persona:
    persona_id: str = "persona-1"
    system_prompt: str = "Use the configured persona."
    style_prompt: str = "Keep replies plain."


def test_final_reply_prompt_uses_tagged_stable_order_and_contexts() -> None:
    packet = build_reply_final_packet(_reply_input())

    assert [section.name for section in packet.sections] == [
        "system_instructions",
        "response_rules",
        "context_priority",
        "persona",
        "style",
        "expression_context",
        "evidence_context",
        "conversation",
        "instruction",
    ]

    rendered = render_flat(packet)
    assert rendered.startswith("<system_instructions>")
    assert "[SystemInstructions]" not in rendered
    assert "<response_rules>" in rendered
    assert "</response_rules>" in rendered
    assert "<expression_context>" in rendered
    assert "档案: - 首选名称: Mika" in rendered
    assert "关系: warm score +24" in rendered
    assert "<evidence_context>" in rendered
    assert rendered.index("工具结果: tool completed") < rendered.index(
        "记忆: likes tests"
    )
    assert rendered.index("记忆: likes tests") < rendered.index("知识: Setup")
    assert rendered.index("知识: Setup") < rendered.index(
        "摘要: 被截断的较早聊天: previous summary"
    )
    assert "若与近期原始聊天冲突，以近期原始聊天为准。" in rendered
    assert "memory-1" not in rendered
    assert "score=0.920" not in rendered
    assert "<conversation>" in rendered
    assert rendered.count("<conversation>") == 1
    assert "Alice: previous message" in rendered
    assert "助手: previous reply" in rendered


def test_planner_prompt_gets_tool_policy_without_expression_context() -> None:
    packet = build_reply_planner_packet(_reply_input())
    names = [section.name for section in packet.sections]

    assert "tool_policy" in names
    assert "expression_context" not in names
    assert names.index("tool_policy") < names.index("evidence_context")
    assert names[:6] == [
        "system_instructions",
        "response_rules",
        "context_priority",
        "persona",
        "style",
        "tool_policy",
    ]


def test_neutral_empty_expression_context_is_omitted() -> None:
    packet = build_reply_final_packet(
        _reply_input(profile_card=(), relationship="neutral score 0")
    )

    assert "expression_context" not in [section.name for section in packet.sections]
    assert "<expression_context>" not in render_flat(packet)


def test_expression_context_omits_raw_relationship_events() -> None:
    packet = build_reply_final_packet(
        _reply_input(
            relationship="\n".join(
                (
                    "关系好感只影响表达层：语气、措辞、主动性、互动距离。",
                    "当前好感：+24 / 范围 [-100, 100]，neutral=0",
                    "关系层级：warm",
                    "近期互动氛围：positive_contact",
                    "近期关系事件：",
                    "- [message] +1 -> 24; user praised the bot",
                )
            ),
        )
    )

    expression_context = next(
        section.content
        for section in packet.sections
        if section.name == "expression_context"
    )
    assert "当前好感：+24" in expression_context
    assert "关系层级：warm" in expression_context
    assert "近期互动氛围：positive_contact" in expression_context
    assert "近期关系事件" not in expression_context
    assert "[message]" not in expression_context


def test_fixed_reply_prompt_text_keeps_necessary_templates_chinese() -> None:
    packet = build_reply_final_packet(_reply_input())
    system_instructions = next(
        section.content
        for section in packet.sections
        if section.name == "system_instructions"
    )
    response_rules = next(
        section.content
        for section in packet.sections
        if section.name == "response_rules"
    )
    context_priority = next(
        section.content
        for section in packet.sections
        if section.name == "context_priority"
    )

    assert _has_han_char(system_instructions) is True
    assert response_rules.startswith(load_prompt_template("reply/response_rules.md"))
    assert "只有在对当前交流有帮助时，才提及工具、记忆或来源。" in response_rules
    assert "群聊中先区分谁在说话" in context_priority
    assert context_priority == load_prompt_template("reply/context_priority.md")
    assert "近期原始聊天优先于更早的对话摘要" in context_priority
    assert _has_han_char(response_rules) is True
    assert _has_han_char(context_priority) is True

    combined = "\n".join((system_instructions, response_rules, context_priority))
    assert "当前任务" not in combined
    assert "完成用户请求" not in combined
    assert "规划文本" not in combined
    assert "agent" not in combined.lower()


def test_conversation_summary_fixed_text_loads_from_chinese_templates() -> None:
    packet = build_conversation_summary_packet(
        ConversationSummaryPromptInput(
            overflow_messages=(
                _turn(
                    message_id="m1",
                    author_role="user",
                    author_id="user-alice",
                    author_name="Alice",
                    text_content="hello",
                ),
            ),
            existing_summary=None,
            scene_type="group",
        )
    )

    instruction = next(
        section.content for section in packet.sections if section.name == "Instruction"
    )
    group_guidance = next(
        section.content
        for section in packet.sections
        if section.name == "GroupGuidance"
    )
    assert instruction == load_prompt_template("conversation_summary/instruction.md")
    assert group_guidance == load_prompt_template(
        "conversation_summary/group_guidance.md"
    )
    assert _has_han_char(instruction) is True
    assert _has_han_char(group_guidance) is True


def test_reply_prompt_regions_keep_only_stable_prefix() -> None:
    projection = project_reply_prompt_regions(build_reply_final_packet(_reply_input()))

    assert [section.name for section in projection.stable] == [
        "system_instructions",
        "response_rules",
        "context_priority",
    ]
    assert "persona" in [section.name for section in projection.dynamic]
    assert "evidence_context" in [section.name for section in projection.dynamic]


def test_prompt_diagnostics_include_full_render_order() -> None:
    from apeiria.ai.prompting import prompt_region_diagnostics

    diagnostics = prompt_region_diagnostics(
        project_reply_prompt_regions(build_reply_final_packet(_reply_input()))
    )

    assert diagnostics["section_names"] == (
        "system_instructions",
        "response_rules",
        "context_priority",
        "persona",
        "style",
        "expression_context",
        "evidence_context",
        "conversation",
        "instruction",
    )


def test_future_task_context_does_not_change_stable_response_rules() -> None:
    ordinary_packet = build_reply_final_packet(_reply_input(future_task_context=None))
    future_task_packet = build_reply_final_packet(
        _reply_input(future_task_context="task_id=task-1")
    )

    ordinary_rules = next(
        section.content
        for section in ordinary_packet.sections
        if section.name == "response_rules"
    )
    future_rules = next(
        section.content
        for section in future_task_packet.sections
        if section.name == "response_rules"
    )
    future_instruction = next(
        section.content
        for section in future_task_packet.sections
        if section.name == "instruction"
    )

    assert future_rules == ordinary_rules
    assert "定时跟进" in future_instruction


def test_summary_memory_is_summary_evidence() -> None:
    packet = build_reply_final_packet(
        _reply_input(
            memories=(_memory(memory_layer="summary", content="older summary"),)
        )
    )
    evidence_context = next(
        section.content
        for section in packet.sections
        if section.name == "evidence_context"
    )

    assert "摘要: older summary" in evidence_context
    assert "记忆: older summary" not in evidence_context


def test_prompt_preview_channels_follow_new_section_shape() -> None:
    from apeiria.app.ai.sessions.prompt_projection import (
        project_prompt_packet_to_channels,
    )

    channels = project_prompt_packet_to_channels(
        build_reply_final_packet(_reply_input()),
        mode="roleplay",
    )

    assert channels.expression_context == (
        "档案: - 首选名称: Mika",
        "关系: warm score +24",
    )
    assert channels.evidence_context == (
        "工具结果: tool completed",
        "记忆: likes tests",
        "知识: Setup (setup.md): Use uv sync.",
        "摘要: 被截断的较早聊天: previous summary",
        "摘要: future task text",
        "摘要: skill text",
    )
    assert not hasattr(channels, "social_policy")
    assert not hasattr(channels, "future_task")
    assert not hasattr(channels, "long_term_memories")


def test_unknown_reply_section_names_do_not_render_as_tags() -> None:
    packet = PromptPacket(
        purpose="reply_final",
        sections=(
            PromptSection(
                role="system",
                name="unknown_section",
                content="unexpected",
            ),
        ),
    )

    assert render_flat(packet) == "[unknown_section]\nunexpected"


def test_unrelated_prompt_packets_keep_existing_renderer_shape() -> None:
    packet = PromptPacket(
        purpose="memory_extraction",
        sections=(
            PromptSection(
                role="system",
                name="MemoryExtraction",
                content="extract memory",
            ),
        ),
    )

    assert render_flat(packet) == "[MemoryExtraction]\nextract memory"
    assert render_messages(packet)[0].content == "[MemoryExtraction]\nextract memory"


def _reply_input(
    *,
    memories: tuple[AIMemoryDefinition, ...] | None = None,
    profile_card: tuple[str, ...] = ("- 首选名称: Mika",),
    relationship: str | None = "warm score +24",
    future_task_context: str | None = "future task text",
) -> ReplyPromptInput:
    return ReplyPromptInput(
        persona=_Persona(),
        scene_type="group",
        relationship=relationship,
        tool_policy="Allowed tools: memory.search",
        tool_results=("tool completed",),
        memories=memories if memories is not None else (_memory(),),
        turns=(
            _turn(
                message_id="m1",
                author_role="user",
                author_id="user-alice",
                author_name="Alice",
                text_content="previous message",
            ),
            _turn(
                message_id="m2",
                author_role="assistant",
                author_id="bot",
                author_name=None,
                text_content="previous reply",
            ),
        ),
        profile_card=profile_card,
        rag_chunks=(_knowledge(),),
        conversation_summary="previous summary",
        tool_guidance="tool guidance text",
        future_task_context=future_task_context,
        skill_activation="skill text",
    )


def _turn(
    *,
    message_id: str,
    author_role: str,
    author_id: str,
    author_name: str | None,
    text_content: str,
) -> ChatContextMessageView:
    return ChatContextMessageView(
        message_id=message_id,
        author_role=author_role,  # type: ignore[arg-type]
        author_id=author_id,
        author_name=author_name,
        text_content=text_content,
        content=None,
        created_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )


def _memory(
    *,
    memory_layer: str = "long_term",
    content: str = "likes tests",
) -> AIMemoryDefinition:
    return AIMemoryDefinition(
        memory_id="memory-1",
        anchor_type="user",
        anchor_id="user-alice",
        memory_layer=memory_layer,  # type: ignore[arg-type]
        memory_kind="preference",
        content=content,
        is_editable=True,
        lifecycle_state="active",
        default_use_mode="context",
        governance_reason=None,
        source_message_id="source-1",
        salience=0.8,
        confidence=0.9,
        last_recalled_at=None,
        created_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
    )


def _knowledge() -> KnowledgeRetrievalItem:
    return KnowledgeRetrievalItem(
        label="K1",
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Setup",
        source_file_name="setup.md",
        rank=1,
        score=0.92,
        rerank_score=0.95,
        excerpt="Use uv sync.",
    )


def _has_han_char(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)
