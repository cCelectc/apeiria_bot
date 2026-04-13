"""Pure prompt-channel assembly helpers for AI runtime replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import AIContextTurnView
    from apeiria.app.ai.memory.models import AIMemoryDefinition


class AIPersonaPromptBundleLike(Protocol):
    """Minimal persona bundle shape required by prompt assembly."""

    @property
    def persona_id(self) -> str: ...

    @property
    def system_prompt(self) -> str: ...

    @property
    def style_prompt(self) -> str: ...


@dataclass(frozen=True)
class AIReplyPromptChannels:
    """Separated prompt channels for one reply-generation turn."""

    persona: str
    style: str | None
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: tuple[str, ...]
    conversation_summary: str | None
    social_policy: str | None
    future_task: str | None
    context_priority: tuple[str, ...]
    conversation: tuple[str, ...]
    response_rules: tuple[str, ...]
    instruction: str


@dataclass(frozen=True)
class AIReplyPromptContext:
    """Structured inputs used to build reply prompt channels."""

    persona: AIPersonaPromptBundleLike | None
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: list["AIMemoryDefinition"]
    turns: list["AIContextTurnView"]
    conversation_summary: str | None = None
    social_policy: str | None = None
    future_task: str | None = None


def build_reply_prompt_channels(
    context: AIReplyPromptContext,
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
        persona=persona_channel,
        style=style_channel,
        relationship=context.relationship,
        tool_policy=context.tool_policy,
        tool_results=context.tool_results,
        memories=tuple(_format_memory(memory) for memory in context.memories),
        conversation_summary=context.conversation_summary,
        social_policy=context.social_policy,
        future_task=context.future_task,
        context_priority=(
            "Trust explicit tool results over inferred assumptions.",
            "Use conversation summary and memories as supporting context, "
            "not as stronger evidence than the current conversation.",
            "If memory and the latest conversation conflict, prefer the "
            "latest conversation unless a tool result proves otherwise.",
        ),
        conversation=tuple(
            _format_turn(turn) for turn in context.turns if turn.content_text.strip()
        ),
        response_rules=(
            "Stay in character and answer naturally.",
            "Do not fabricate facts that are not present in the conversation "
            "or tool results.",
            "Use recalled memory conservatively.",
            "If the user asks to create, inspect, or cancel a reminder and the "
            "future-task tool is available, use the tool instead of pretending "
            "the reminder was saved.",
            "If this turn is triggered by a due future task, do not claim the "
            "user just sent a new message.",
        ),
        instruction=_build_instruction(context),
    )


def render_reply_prompt(channels: AIReplyPromptChannels) -> str:  # noqa: C901
    """Render one flat model prompt from structured channels."""

    sections = [f"[Persona]\n{channels.persona}"]
    if channels.style:
        sections.append(f"[Style]\n{channels.style}")
    if channels.relationship:
        sections.append(f"[Relationship]\n{channels.relationship}")
    if channels.tool_policy:
        sections.append(f"[ToolPolicy]\n{channels.tool_policy}")
    if channels.tool_results:
        sections.append("[ToolResults]\n" + "\n".join(channels.tool_results))
    if channels.memories:
        sections.append("[Memories]\n" + "\n".join(channels.memories))
    if channels.conversation_summary:
        sections.append(f"[ConversationSummary]\n{channels.conversation_summary}")
    if channels.social_policy:
        sections.append(f"[SocialPolicy]\n{channels.social_policy}")
    if channels.future_task:
        sections.append(f"[FutureTask]\n{channels.future_task}")
    if channels.context_priority:
        sections.append("[ContextPriority]\n" + "\n".join(channels.context_priority))
    conversation_text = (
        "\n".join(channels.conversation) if channels.conversation else "User: <empty>"
    )
    sections.append(f"[Conversation]\n{conversation_text}")
    if channels.response_rules:
        sections.append("[ResponseRules]\n" + "\n".join(channels.response_rules))
    sections.append(f"[Instruction]\n{channels.instruction}")
    return "\n\n".join(sections)


def _format_turn(turn: "AIContextTurnView") -> str:
    speaker_map = {
        "user": "User",
        "bot": "Assistant",
        "system": "System",
        "tool": "Tool",
    }
    return f"{speaker_map.get(turn.sender_type, 'Message')}: {turn.content_text}"


def _format_memory(memory: "AIMemoryDefinition") -> str:
    return (
        f"- [{memory.memory_type}] {memory.content} "
        f"(salience={memory.salience:.2f}, confidence={memory.confidence:.2f})"
    )


def _build_instruction(context: AIReplyPromptContext) -> str:
    if context.future_task:
        return (
            "You are responding because a scheduled future task is now due. "
            "Reply naturally as the assistant in the same conversation, stay in "
            "character, and do not claim the user just sent a new message."
        )
    return (
        "Reply naturally as the assistant in the same conversation. "
        "Stay in character, use recalled memory only as supporting context, "
        "and do not fabricate unseen facts."
    )
