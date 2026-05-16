"""Reply-generation prompt recipes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from .models import PromptPacket, PromptSection, PromptSectionRole
from .regions import PromptRegionProjection, project_prompt_regions
from .template_loader import load_prompt_template_lines

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.knowledge.models import KnowledgeRetrievalItem
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.conversation.models import ChatContextMessageView

ReplyPromptMode = Literal["planner", "roleplay"]
_GROUP_USER_ID_SUFFIX_LENGTH = 4
_REPLY_SYSTEM_INSTRUCTIONS = {
    "planner": (
        "你正在判断当前聊天轮次应该如何处理。",
        "如果会生成用户可见内容，必须保持人格语气稳定。",
        "只有在能提升正确性或完成用户明确请求时，才使用工具。",
    ),
    "roleplay": (
        "你正在为当前聊天轮次写最终可见回复。",
        "只输出用户可见的回复内容，并保持人格语气稳定。",
        "工具结果、记忆和对话上下文只有在与当前回复相关时才使用。",
    ),
}
_REPLY_RESPONSE_RULES = {
    "planner": "只调用为保证正确性或完成用户请求所必需的最少工具。",
    "roleplay": "只有在对用户有帮助时，才提及工具、记忆或来源。",
}
_REPLY_INSTRUCTIONS = {
    "planner": (
        "决定下一步动作。如果需要工具，只调用为保证正确性或完成用户请求"
        "所必需的最少工具。如果现有上下文已经足够支持回答，"
        "就直接以人格语气回复。不要暴露规划文本。"
    ),
    "roleplay": "只写当前聊天轮次的最终助手回复。",
    "scheduled_planner": "为同一个聊天会话中的定时跟进回复做规划。",
    "scheduled_roleplay": "写出同一个聊天会话中的定时跟进回复。",
}
REPLY_SECTION_SYSTEM_INSTRUCTIONS = "system_instructions"
REPLY_SECTION_RESPONSE_RULES = "response_rules"
REPLY_SECTION_CONTEXT_PRIORITY = "context_priority"
REPLY_SECTION_PERSONA = "persona"
REPLY_SECTION_STYLE = "style"
REPLY_SECTION_TOOL_POLICY = "tool_policy"
REPLY_SECTION_EXPRESSION_CONTEXT = "expression_context"
REPLY_SECTION_EVIDENCE_CONTEXT = "evidence_context"
REPLY_SECTION_CONVERSATION = "conversation"
REPLY_SECTION_INSTRUCTION = "instruction"
REPLY_STABLE_REGION_SECTIONS = (
    REPLY_SECTION_SYSTEM_INSTRUCTIONS,
    REPLY_SECTION_RESPONSE_RULES,
    REPLY_SECTION_CONTEXT_PRIORITY,
)
REPLY_SECTION_TAG_NAMES = (
    *REPLY_STABLE_REGION_SECTIONS,
    REPLY_SECTION_PERSONA,
    REPLY_SECTION_STYLE,
    REPLY_SECTION_TOOL_POLICY,
    REPLY_SECTION_EXPRESSION_CONTEXT,
    REPLY_SECTION_EVIDENCE_CONTEXT,
    REPLY_SECTION_CONVERSATION,
    REPLY_SECTION_INSTRUCTION,
)


class ReplyPersonaPromptBundleLike(Protocol):
    """Minimal persona bundle shape required by reply prompt recipes."""

    @property
    def persona_id(self) -> str: ...

    @property
    def system_prompt(self) -> str: ...

    @property
    def style_prompt(self) -> str: ...


@dataclass(frozen=True)
class ReplyPromptInput:
    """Prompt-facing materials for one reply-generation model call."""

    persona: ReplyPersonaPromptBundleLike | None
    scene_type: str
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: "Sequence[AIMemoryDefinition]"
    turns: "Sequence[ChatContextMessageView]"
    profile_card: tuple[str, ...]
    rag_chunks: "Sequence[KnowledgeRetrievalItem]" = ()
    conversation_summary: str | None = None
    tool_guidance: str | None = None
    future_task_context: str | None = None
    skill_activation: str | None = None


def build_reply_planner_packet(inputs: ReplyPromptInput) -> PromptPacket:
    """Build the tool-capable reply-planning packet."""

    return _build_reply_packet(inputs, mode="planner")


def build_reply_final_packet(inputs: ReplyPromptInput) -> PromptPacket:
    """Build the direct or post-tool visible reply packet."""

    return _build_reply_packet(inputs, mode="roleplay")


def _build_reply_packet(
    inputs: ReplyPromptInput,
    *,
    mode: ReplyPromptMode,
) -> PromptPacket:
    sections: list[PromptSection] = []
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_SYSTEM_INSTRUCTIONS,
        content="\n".join(_build_system_instructions(mode)),
    )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_RESPONSE_RULES,
        lines=_build_response_rules(mode),
    )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_CONTEXT_PRIORITY,
        lines=_build_context_priority(),
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_PERSONA,
        content=(
            inputs.persona.system_prompt
            if inputs.persona is not None
            else "你是当前对话中的自然聊天参与者。"
        ),
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_STYLE,
        content=(
            inputs.persona.style_prompt
            if inputs.persona is not None and inputs.persona.style_prompt
            else None
        ),
    )
    if mode == "planner":
        _append_section(
            sections,
            role="system",
            name=REPLY_SECTION_TOOL_POLICY,
            content=_build_tool_policy_context(inputs),
        )
    if mode != "planner":
        _append_lines(
            sections,
            role="system",
            name=REPLY_SECTION_EXPRESSION_CONTEXT,
            lines=_build_expression_context(inputs),
        )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_EVIDENCE_CONTEXT,
        lines=_build_evidence_context(inputs),
    )
    _append_conversation_sections(sections, inputs.turns, scene_type=inputs.scene_type)
    _append_section(
        sections,
        role="user",
        name=REPLY_SECTION_INSTRUCTION,
        content=_build_instruction(inputs, mode),
    )
    return PromptPacket(
        purpose="reply_planner" if mode == "planner" else "reply_final",
        sections=tuple(sections),
    )


def project_reply_prompt_regions(packet: PromptPacket) -> PromptRegionProjection:
    """Project a reply prompt packet into stable and dynamic regions."""

    return project_prompt_regions(
        packet,
        stable_section_names=REPLY_STABLE_REGION_SECTIONS,
    )


def _build_tool_policy_context(inputs: ReplyPromptInput) -> str | None:
    lines: list[str] = []
    if inputs.tool_policy:
        lines.append(inputs.tool_policy.strip())
    if inputs.tool_guidance:
        lines.append(inputs.tool_guidance.strip())
    return "\n".join(lines) if lines else None


def _build_expression_context(inputs: ReplyPromptInput) -> tuple[str, ...]:
    lines = [f"档案: {line}" for line in _clean_lines(inputs.profile_card)]
    relationship = _expression_relationship_line(inputs.relationship)
    if relationship is not None:
        lines.append(f"关系: {relationship}")
    return tuple(lines)


def _expression_relationship_line(relationship: str | None) -> str | None:
    if relationship is None or not relationship.strip():
        return None
    text = _strip_relationship_diagnostics(relationship)
    if not text:
        return None
    normalized = text.lower()
    if normalized in {"neutral", "neutral score 0", "score 0", "0"}:
        return None
    if "neutral=0" in normalized and "近期互动氛围：" not in text:
        return None
    return text


def _strip_relationship_diagnostics(relationship: str) -> str:
    lines: list[str] = []
    for line in _clean_lines(relationship.splitlines()):
        if line.startswith("近期关系事件"):
            break
        lines.append(line)
    return "\n".join(lines)


def _build_evidence_context(inputs: ReplyPromptInput) -> tuple[str, ...]:
    lines: list[str] = []
    lines.extend(f"工具结果: {line}" for line in _clean_lines(inputs.tool_results))
    lines.extend(
        f"记忆: {line}"
        for line in _format_memories(inputs.memories, layers=("operator", "long_term"))
    )
    lines.extend(
        f"知识: {line}"
        for line in _format_memories(inputs.memories, layers=("knowledge",))
    )
    lines.extend(f"知识: {line}" for line in _format_knowledge(inputs.rag_chunks))
    lines.extend(
        f"摘要: {line}"
        for line in _format_memories(inputs.memories, layers=("summary",))
    )
    lines.extend(f"摘要: {line}" for line in _build_summary_lines(inputs))
    return tuple(lines)


def _format_memories(
    memories: "Sequence[AIMemoryDefinition]",
    *,
    layers: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        _format_memory(memory)
        for layer in layers
        for memory in memories
        if memory.memory_layer == layer
    )


def _format_knowledge(
    rag_chunks: "Sequence[KnowledgeRetrievalItem]",
) -> tuple[str, ...]:
    return tuple(_format_rag_chunk(chunk) for chunk in rag_chunks)


def _build_summary_lines(inputs: ReplyPromptInput) -> tuple[str, ...]:
    lines: list[str] = []
    lines.extend(_clean_lines((inputs.conversation_summary,)))
    lines.extend(_clean_lines((inputs.future_task_context,)))
    lines.extend(_clean_lines((inputs.skill_activation,)))
    return tuple(lines)


def _append_conversation_sections(
    sections: list[PromptSection],
    turns: "Sequence[ChatContextMessageView]",
    *,
    scene_type: str,
) -> None:
    lines: list[str] = []
    for turn in turns:
        if not turn.text_content.strip():
            continue
        lines.append(_format_turn(turn, scene_type=scene_type))
    _append_section(
        sections,
        role="user",
        name=REPLY_SECTION_CONVERSATION,
        content="\n".join(lines) if lines else "用户: <空>",
    )


def _append_section(
    sections: list[PromptSection],
    *,
    role: PromptSectionRole,
    name: str,
    content: str | None,
) -> None:
    if content is None or not content.strip():
        return
    sections.append(PromptSection(role=role, name=name, content=content))


def _append_lines(
    sections: list[PromptSection],
    *,
    role: PromptSectionRole,
    name: str,
    lines: tuple[str, ...],
) -> None:
    content = "\n".join(line for line in lines if line.strip())
    _append_section(sections, role=role, name=name, content=content)


def _build_context_priority() -> tuple[str, ...]:
    return load_prompt_template_lines("reply/context_priority.md")


def _build_system_instructions(mode: ReplyPromptMode) -> tuple[str, ...]:
    return _REPLY_SYSTEM_INSTRUCTIONS[mode]


def _format_turn(
    turn: "ChatContextMessageView",
    *,
    scene_type: str,
) -> str:
    if turn.author_role == "user":
        speaker = _format_user_label(turn, scene_type=scene_type)
    elif turn.author_role == "assistant":
        speaker = "助手"
    elif turn.author_role == "tool":
        speaker = f"工具[{turn.author_id}]"
    elif turn.author_role == "system":
        speaker = "系统"
    else:
        speaker = "消息"
    return f"{speaker}: {turn.text_content}"


def _format_user_label(
    turn: "ChatContextMessageView",
    *,
    scene_type: str,
) -> str:
    author_name = (turn.author_name or "").strip()
    if scene_type == "group":
        if author_name:
            return author_name
        suffix = (
            turn.author_id[-_GROUP_USER_ID_SUFFIX_LENGTH:]
            if len(turn.author_id) > _GROUP_USER_ID_SUFFIX_LENGTH
            else turn.author_id
        )
        return f"用户#{suffix}"
    return author_name or "用户"


def _format_memory(memory: "AIMemoryDefinition") -> str:
    return memory.content


def _format_rag_chunk(chunk: "KnowledgeRetrievalItem") -> str:
    source = f" ({chunk.source_file_name})" if chunk.source_file_name else ""
    return f"{chunk.title}{source}: {chunk.excerpt}"


def _build_response_rules(mode: ReplyPromptMode) -> tuple[str, ...]:
    rules = list(load_prompt_template_lines("reply/response_rules.md"))
    rules.append(_REPLY_RESPONSE_RULES[mode])
    return tuple(rules)


def _build_instruction(
    inputs: ReplyPromptInput,
    mode: ReplyPromptMode,
) -> str:
    if inputs.future_task_context:
        scheduled_mode = f"scheduled_{mode}"
        return _REPLY_INSTRUCTIONS[scheduled_mode]
    return _REPLY_INSTRUCTIONS[mode]


def _clean_lines(lines: "Sequence[str | None]") -> tuple[str, ...]:
    return tuple(line.strip() for line in lines if line is not None and line.strip())
