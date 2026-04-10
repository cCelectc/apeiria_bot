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
    conversation: tuple[str, ...]
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
        conversation=tuple(
            _format_turn(turn)
            for turn in context.turns
            if turn.content_text.strip()
        ),
        instruction=(
            "Reply naturally as the assistant in the same conversation. "
            "Stay in character, use recalled memory only as supporting context, "
            "and do not fabricate unseen facts."
        ),
    )


def render_reply_prompt(channels: AIReplyPromptChannels) -> str:
    """Render one flat provider prompt from structured channels."""

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
    conversation_text = (
        "\n".join(channels.conversation)
        if channels.conversation
        else "User: <empty>"
    )
    sections.append(f"[Conversation]\n{conversation_text}")
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
