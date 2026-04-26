"""Pure prompt-channel assembly helpers for AI runtime replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.conversation.models import ChatContextMessageView

AIPromptMode = Literal["planner", "roleplay"]
_GROUP_USER_ID_SUFFIX_LENGTH = 4


class AIPersonaPromptBundleLike(Protocol):
    """Minimal persona bundle shape required by prompt assembly."""

    @property
    def persona_id(self) -> str: ...

    @property
    def system_prompt(self) -> str: ...

    @property
    def style_prompt(self) -> str: ...


@dataclass(frozen=True)
class AIPromptSystemChannels:
    """System and persona-facing prompt channels."""

    instructions: tuple[str, ...]
    persona: str
    style: str | None
    relationship: str | None
    social_policy: str | None
    tool_policy: str | None
    future_task: str | None


@dataclass(frozen=True)
class AIPromptMemoryChannels:
    """Memory channels grouped by layer."""

    operator: tuple[str, ...]
    summary: tuple[str, ...]
    long_term: tuple[str, ...]
    knowledge: tuple[str, ...]


@dataclass(frozen=True)
class AIPromptConversationChannel:
    """Conversation-facing prompt channels."""

    summary: str | None
    context_priority: tuple[str, ...]
    messages: tuple[str, ...]


@dataclass(frozen=True)
class AIReplyPromptChannels:
    """Separated prompt channels for one reply-generation turn."""

    mode: AIPromptMode
    system: AIPromptSystemChannels
    person_profile: tuple[str, ...]
    memories: AIPromptMemoryChannels
    tool_results: tuple[str, ...]
    conversation: AIPromptConversationChannel
    response_rules: tuple[str, ...]
    instruction: str
    skill_activation: str | None = None


@dataclass(frozen=True)
class AIReplyPromptContext:
    """Structured inputs used to build reply prompt channels."""

    persona: AIPersonaPromptBundleLike | None
    scene_type: str
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: list["AIMemoryDefinition"]
    turns: list["ChatContextMessageView"]
    person_profile: tuple[str, ...]
    conversation_summary: str | None = None
    social_policy: str | None = None
    future_task: str | None = None
    skill_activation: str | None = None


def build_reply_prompt_channels(
    context: AIReplyPromptContext,
    *,
    mode: AIPromptMode,
) -> AIReplyPromptChannels:
    """Build separated prompt channels for one social reply."""

    persona_channel = (
        context.persona.system_prompt
        if context.persona is not None
        else "You are a helpful social AI in a chat."
    )
    style_channel = (
        context.persona.style_prompt
        if context.persona and context.persona.style_prompt
        else None
    )
    return AIReplyPromptChannels(
        mode=mode,
        system=AIPromptSystemChannels(
            instructions=_build_system_instructions(mode),
            persona=persona_channel,
            style=style_channel,
            relationship=context.relationship,
            social_policy=context.social_policy,
            tool_policy=context.tool_policy if mode == "planner" else None,
            future_task=context.future_task,
        ),
        person_profile=context.person_profile,
        memories=AIPromptMemoryChannels(
            operator=tuple(
                _format_memory(memory)
                for memory in context.memories
                if memory.memory_layer == "operator"
            ),
            summary=tuple(
                _format_memory(memory)
                for memory in context.memories
                if memory.memory_layer == "summary"
            ),
            long_term=tuple(
                _format_memory(memory)
                for memory in context.memories
                if memory.memory_layer == "long_term"
            ),
            knowledge=tuple(
                _format_memory(memory)
                for memory in context.memories
                if memory.memory_layer == "knowledge"
            ),
        ),
        tool_results=context.tool_results,
        conversation=AIPromptConversationChannel(
            summary=context.conversation_summary,
            context_priority=(
                "Trust explicit tool results over inferred assumptions.",
                "Use conversation summary and memories as supporting context "
                "for the active exchange.",
                "Prefer the latest conversation when it carries fresher detail.",
            ),
            messages=tuple(
                _format_turn(turn, scene_type=context.scene_type)
                for turn in context.turns
                if turn.text_content.strip()
            ),
        ),
        response_rules=_build_response_rules(context, mode),
        instruction=_build_instruction(context, mode),
        skill_activation=context.skill_activation,
    )


def render_reply_prompt(channels: AIReplyPromptChannels) -> str:  # noqa: C901, PLR0912
    """Render one flat model prompt from structured channels."""

    sections = ["[SystemInstructions]\n" + "\n".join(channels.system.instructions)]
    sections.append(f"[Persona]\n{channels.system.persona}")
    if channels.system.style:
        sections.append(f"[Style]\n{channels.system.style}")
    if channels.system.relationship:
        sections.append(f"[Relationship]\n{channels.system.relationship}")
    if channels.person_profile:
        sections.append("[PersonProfile]\n" + "\n".join(channels.person_profile))
    if channels.system.social_policy:
        sections.append(f"[SocialPolicy]\n{channels.system.social_policy}")
    if channels.system.tool_policy:
        sections.append(f"[ToolPolicy]\n{channels.system.tool_policy}")
    if channels.tool_results:
        sections.append("[ToolResults]\n" + "\n".join(channels.tool_results))
    if channels.memories.operator:
        sections.append("[OperatorMemories]\n" + "\n".join(channels.memories.operator))
    if channels.memories.summary:
        sections.append("[SummaryMemories]\n" + "\n".join(channels.memories.summary))
    if channels.memories.long_term:
        sections.append("[LongTermMemories]\n" + "\n".join(channels.memories.long_term))
    if channels.memories.knowledge:
        sections.append(
            "[KnowledgeMemories]\n" + "\n".join(channels.memories.knowledge)
        )
    if channels.conversation.summary:
        sections.append(f"[ConversationSummary]\n{channels.conversation.summary}")
    if channels.system.future_task:
        sections.append(f"[FutureTask]\n{channels.system.future_task}")
    if channels.skill_activation:
        sections.append(f"[ActiveSkills]\n{channels.skill_activation}")
    if channels.conversation.context_priority:
        sections.append(
            "[ContextPriority]\n" + "\n".join(channels.conversation.context_priority)
        )
    conversation_text = (
        "\n".join(channels.conversation.messages)
        if channels.conversation.messages
        else "User: <empty>"
    )
    sections.append(f"[Conversation]\n{conversation_text}")
    if channels.response_rules:
        sections.append("[ResponseRules]\n" + "\n".join(channels.response_rules))
    sections.append(f"[Instruction]\n{channels.instruction}")
    return "\n\n".join(sections)


def _build_system_instructions(mode: AIPromptMode) -> tuple[str, ...]:
    if mode == "planner":
        return (
            "You are planning the next assistant action for an ongoing chat session.",
            "Keep the persona voice stable in any visible text you generate.",
            "Use tools only when they improve correctness or complete a "
            "requested action.",
        )
    return (
        "You are writing the final assistant reply for an ongoing chat session.",
        "Produce only the user-visible reply and keep the persona voice stable.",
        "Use tool results, memory, and conversation context to produce one "
        "coherent reply.",
    )


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


def _build_response_rules(
    context: AIReplyPromptContext,
    mode: AIPromptMode,
) -> tuple[str, ...]:
    rules = [
        "Stay in character and answer naturally.",
        "Ground factual claims in the conversation, tool results, and recalled memory.",
        "Use recalled memory as supporting context for the active exchange.",
        (
            "Relationship context modulates only your expression layer — "
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
            "Write one final assistant reply that integrates the strongest "
            "available context."
        )
        rules.append(
            "Keep tool usage implicit unless the user-facing result should mention it."
        )
    if context.future_task:
        rules.append(
            "Treat this turn as a scheduled follow-up inside the same chat session."
        )
    return tuple(rules)


def _build_instruction(
    context: AIReplyPromptContext,
    mode: AIPromptMode,
) -> str:
    if context.future_task:
        if mode == "planner":
            return "Plan the scheduled follow-up reply for the same chat session."
        return "Write the scheduled follow-up reply for the same chat session."
    if mode == "planner":
        return "Decide whether to reply directly or call tools for this chat turn."
    return "Write only the final assistant reply for this chat turn."
