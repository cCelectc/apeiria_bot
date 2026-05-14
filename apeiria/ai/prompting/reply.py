"""Reply-generation prompt recipes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from .models import PromptPacket, PromptSection, PromptSectionRole
from .regions import PromptRegionProjection, project_prompt_regions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from apeiria.ai.knowledge.models import KnowledgeRetrievalItem
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.conversation.models import ChatContextMessageView

ReplyPromptMode = Literal["planner", "roleplay"]
_GROUP_USER_ID_SUFFIX_LENGTH = 4
REPLY_SECTION_SYSTEM_INSTRUCTIONS = "SystemInstructions"
REPLY_SECTION_PERSONA = "Persona"
REPLY_SECTION_STYLE = "Style"
REPLY_SECTION_CAPABILITY_AWARENESS = "CapabilityAwareness"
REPLY_SECTION_TOOL_GUIDANCE = "ToolGuidance"
REPLY_SECTION_RELATIONSHIP = "Relationship"
REPLY_SECTION_PERSON_PROFILE = "PersonProfile"
REPLY_SECTION_SOCIAL_POLICY = "SocialPolicy"
REPLY_SECTION_TOOL_POLICY = "ToolPolicy"
REPLY_SECTION_TOOL_RESULTS = "ToolResults"
REPLY_SECTION_OPERATOR_MEMORIES = "OperatorMemories"
REPLY_SECTION_SUMMARY_MEMORIES = "SummaryMemories"
REPLY_SECTION_LONG_TERM_MEMORIES = "LongTermMemories"
REPLY_SECTION_KNOWLEDGE_MEMORIES = "KnowledgeMemories"
REPLY_SECTION_RAG_KNOWLEDGE = "RAGKnowledge"
REPLY_SECTION_CONVERSATION_SUMMARY = "ConversationSummary"
REPLY_SECTION_FUTURE_TASK = "FutureTask"
REPLY_SECTION_ACTIVE_SKILLS = "ActiveSkills"
REPLY_SECTION_CONTEXT_PRIORITY = "ContextPriority"
REPLY_SECTION_RESPONSE_RULES = "ResponseRules"
REPLY_SECTION_CONVERSATION = "Conversation"
REPLY_SECTION_INSTRUCTION = "Instruction"
REPLY_STABLE_REGION_SECTIONS = (
    REPLY_SECTION_SYSTEM_INSTRUCTIONS,
    REPLY_SECTION_PERSONA,
    REPLY_SECTION_STYLE,
    REPLY_SECTION_CAPABILITY_AWARENESS,
    REPLY_SECTION_TOOL_GUIDANCE,
    REPLY_SECTION_RESPONSE_RULES,
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
    person_profile: tuple[str, ...]
    rag_chunks: "Sequence[KnowledgeRetrievalItem]" = ()
    conversation_summary: str | None = None
    social_policy_summary: str | None = None
    capability_awareness: str | None = None
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
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_PERSONA,
        content=(
            inputs.persona.system_prompt
            if inputs.persona is not None
            else "You are a chat participant in an ongoing conversation."
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
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_CAPABILITY_AWARENESS,
        content=inputs.capability_awareness,
    )
    if mode == "planner":
        _append_section(
            sections,
            role="system",
            name=REPLY_SECTION_TOOL_GUIDANCE,
            content=inputs.tool_guidance,
        )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_RESPONSE_RULES,
        lines=_build_response_rules(inputs, mode),
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_RELATIONSHIP,
        content=inputs.relationship,
    )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_PERSON_PROFILE,
        lines=inputs.person_profile,
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_SOCIAL_POLICY,
        content=inputs.social_policy_summary,
    )
    if mode == "planner":
        _append_section(
            sections,
            role="system",
            name=REPLY_SECTION_TOOL_POLICY,
            content=inputs.tool_policy,
        )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_TOOL_RESULTS,
        lines=inputs.tool_results,
    )
    _append_memory_sections(sections, inputs.memories)
    _append_rag_section(sections, inputs.rag_chunks)
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_CONVERSATION_SUMMARY,
        content=inputs.conversation_summary,
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_FUTURE_TASK,
        content=inputs.future_task_context,
    )
    _append_section(
        sections,
        role="system",
        name=REPLY_SECTION_ACTIVE_SKILLS,
        content=inputs.skill_activation,
    )
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_CONTEXT_PRIORITY,
        lines=_build_context_priority(),
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


def _append_memory_sections(
    sections: list[PromptSection],
    memories: "Sequence[AIMemoryDefinition]",
) -> None:
    for name, layer in (
        (REPLY_SECTION_OPERATOR_MEMORIES, "operator"),
        (REPLY_SECTION_SUMMARY_MEMORIES, "summary"),
        (REPLY_SECTION_LONG_TERM_MEMORIES, "long_term"),
        (REPLY_SECTION_KNOWLEDGE_MEMORIES, "knowledge"),
    ):
        _append_lines(
            sections,
            role="system",
            name=name,
            lines=tuple(
                _format_memory(memory)
                for memory in memories
                if memory.memory_layer == layer
            ),
        )


def _append_rag_section(
    sections: list[PromptSection],
    rag_chunks: "Sequence[KnowledgeRetrievalItem]",
) -> None:
    _append_lines(
        sections,
        role="system",
        name=REPLY_SECTION_RAG_KNOWLEDGE,
        lines=tuple(_format_rag_chunk(chunk) for chunk in rag_chunks),
    )


def _append_conversation_sections(
    sections: list[PromptSection],
    turns: "Sequence[ChatContextMessageView]",
    *,
    scene_type: str,
) -> None:
    appended = False
    for turn in turns:
        if not turn.text_content.strip():
            continue
        appended = True
        _append_section(
            sections,
            role=_conversation_section_role(turn),
            name=REPLY_SECTION_CONVERSATION,
            content=_format_turn(turn, scene_type=scene_type),
        )
    if not appended:
        _append_section(
            sections,
            role="user",
            name=REPLY_SECTION_CONVERSATION,
            content="User: <empty>",
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
    return (
        "Trust explicit tool results over inferred assumptions.",
        "Use conversation summary and memories only as relevant supporting "
        "context for the active exchange.",
        "Prefer the latest conversation when it carries fresher detail.",
    )


def _build_system_instructions(mode: ReplyPromptMode) -> tuple[str, ...]:
    if mode == "planner":
        return (
            "You are deciding how to handle the current turn in an ongoing chat.",
            "Keep the persona voice stable in any visible text you generate.",
            "Use tools only when they improve correctness or complete a "
            "requested action.",
        )
    return (
        "You are writing the final visible reply for the current chat turn.",
        "Produce only the user-visible reply and keep the persona voice stable.",
        "Use tool results, memory, and conversation context only when they are "
        "relevant to the reply.",
    )


def _conversation_section_role(
    turn: "ChatContextMessageView",
) -> PromptSectionRole:
    if turn.author_role == "assistant":
        return "assistant"
    return "user"


def _format_turn(
    turn: "ChatContextMessageView",
    *,
    scene_type: str,
) -> str:
    if turn.author_role == "user":
        speaker = _format_user_label(turn, scene_type=scene_type)
    elif turn.author_role == "assistant":
        speaker = "Assistant"
    elif turn.author_role == "tool":
        speaker = f"Tool[{turn.author_id}]"
    elif turn.author_role == "system":
        speaker = "System"
    else:
        speaker = "Message"
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
        return f"User#{suffix}"
    return author_name or "User"


def _format_memory(memory: "AIMemoryDefinition") -> str:
    return (
        f"- [{memory.memory_layer}/{memory.memory_kind}] {memory.content} "
        f"(salience={memory.salience:.2f}, confidence={memory.confidence:.2f})"
    )


def _format_rag_chunk(chunk: "KnowledgeRetrievalItem") -> str:
    return (
        f"- [{chunk.label}] {chunk.title} ({chunk.source_file_name}) "
        f"rank={chunk.rank} score={chunk.score:.3f}: {chunk.excerpt}"
    )


def _build_response_rules(
    inputs: ReplyPromptInput,
    mode: ReplyPromptMode,
) -> tuple[str, ...]:
    rules = [
        "Stay in character and answer naturally.",
        (
            "For ordinary chat, prefer concise, natural replies instead of "
            "summaries, plans, or task-oriented wrap-ups."
        ),
        (
            "Do not end with a follow-up question by default; ask only when a "
            "useful answer needs missing essential information or the user "
            "explicitly asks you to continue."
        ),
        (
            "Avoid assistant-style task offers, summaries, next steps, and "
            "wrap-up lines unless the user clearly asks for task help."
        ),
        (
            "Longer answers are fine for explicit tasks such as explanations, "
            "analysis, planning, decisions, or concrete requested actions."
        ),
        "Ground factual claims in relevant conversation, tool results, and memory.",
        "Use recalled memory only when it supports the active exchange.",
        (
            "Relationship context modulates only your expression layer - "
            "warmth, distance, initiative, and phrasing style. "
            "It must never override, weaken, or replace any aspect of "
            "the persona core (identity, goals, personality traits, speech patterns)."
        ),
    ]
    if mode == "planner":
        rules.append(
            "Call tools with focused arguments when they improve correctness or "
            "complete a requested action."
        )
        rules.append("Use direct reply when the existing context already supports it.")
        rules.append(
            "Keep internal planning and policy language out of the visible reply."
        )
    else:
        rules.append(
            "Write one final reply to the current turn; a short direct reply "
            "is valid when enough."
        )
        rules.append(
            "Keep tool usage implicit unless the user-facing result should mention it."
        )
    if inputs.future_task_context:
        rules.append(
            "Treat this turn as a scheduled follow-up inside the same chat session."
        )
    return tuple(rules)


def _build_instruction(
    inputs: ReplyPromptInput,
    mode: ReplyPromptMode,
) -> str:
    if inputs.future_task_context:
        if mode == "planner":
            return "Plan the scheduled follow-up reply for the same chat session."
        return "Write the scheduled follow-up reply for the same chat session."
    if mode == "planner":
        return "Decide whether to reply directly or call tools for this chat turn."
    return "Write only the final assistant reply for this chat turn."
