"""Convert prompt channels and conversation turns into AIModelMessage arrays."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model import AIModelMessage

if TYPE_CHECKING:
    from apeiria.ai.pipeline.prompting import AIReplyPromptChannels
    from apeiria.conversation.models import ChatContextMessageView


def build_system_message(channels: AIReplyPromptChannels) -> AIModelMessage:
    """Build a single system message from all system-level prompt channels."""

    sections: list[str] = []

    # System instructions
    if channels.system.instructions:
        sections.append("\n".join(channels.system.instructions))

    # Persona core
    sections.append(channels.system.persona)

    # Style + relationship + person profile + social policy + tool policy
    _append_system_context_sections(sections, channels)

    # Memories
    _append_memory_sections(sections, channels)

    # Conversation summary + future task + context priority
    _append_conversation_context_sections(sections, channels)

    # Response rules + instruction
    if channels.response_rules:
        sections.append("[ResponseRules]\n" + "\n".join(channels.response_rules))
    sections.append(f"[Instruction]\n{channels.instruction}")

    return AIModelMessage(
        role="system",
        content="\n\n".join(sections),
    )


def _append_system_context_sections(
    sections: list[str],
    channels: AIReplyPromptChannels,
) -> None:
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


def _append_memory_sections(
    sections: list[str],
    channels: AIReplyPromptChannels,
) -> None:
    for label, items in (
        ("OperatorMemories", channels.memories.operator),
        ("SummaryMemories", channels.memories.summary),
        ("LongTermMemories", channels.memories.long_term),
        ("KnowledgeMemories", channels.memories.knowledge),
    ):
        if items:
            sections.append(f"[{label}]\n" + "\n".join(items))


def _append_conversation_context_sections(
    sections: list[str],
    channels: AIReplyPromptChannels,
) -> None:
    if channels.conversation.summary:
        sections.append(f"[ConversationSummary]\n{channels.conversation.summary}")
    if channels.system.future_task:
        sections.append(f"[FutureTask]\n{channels.system.future_task}")
    if channels.conversation.context_priority:
        sections.append(
            "[ContextPriority]\n" + "\n".join(channels.conversation.context_priority)
        )


def build_conversation_messages(
    turns: list[ChatContextMessageView],
) -> tuple[AIModelMessage, ...]:
    """Convert conversation turns into user/assistant messages."""

    messages: list[AIModelMessage] = []
    for turn in turns:
        if not turn.text_content.strip():
            continue
        if turn.author_role == "user":
            label = (turn.author_name or "").strip()
            content = f"{label}: {turn.text_content}" if label else turn.text_content
            messages.append(AIModelMessage(role="user", content=content))
        elif turn.author_role == "assistant":
            messages.append(AIModelMessage(role="assistant", content=turn.text_content))
        elif turn.author_role == "tool":
            messages.append(
                AIModelMessage(role="user", content=f"[Tool] {turn.text_content}")
            )
        elif turn.author_role == "system":
            messages.append(
                AIModelMessage(role="user", content=f"[System] {turn.text_content}")
            )

    return tuple(messages)


def build_chat_messages(
    channels: AIReplyPromptChannels,
    turns: list[ChatContextMessageView],
) -> tuple[AIModelMessage, ...]:
    """Build a complete messages array from prompt channels and turns.

    Returns ``(system_message, ...conversation_messages)``.
    """

    system = build_system_message(channels)
    conversation = build_conversation_messages(turns)
    return (system, *conversation)
