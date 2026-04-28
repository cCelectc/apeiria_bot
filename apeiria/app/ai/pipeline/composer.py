"""Runtime prompt composition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.prompting import (
    PromptPacket,
    ReplyPromptInput,
    ReplyPromptMode,
    build_reply_final_packet,
    build_reply_planner_packet,
    render_messages,
)

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class AIRuntimeComposeInput:
    """Structured runtime inputs for reply prompt composition."""

    persona: "ReplyPersonaPromptBundleLike | None"
    scene_type: str
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: list["AIMemoryDefinition"]
    turns: list["ChatContextMessageView"]
    person_profile: tuple[str, ...]
    conversation_summary: str | None = None
    social_policy_summary: str | None = None
    capability_awareness: str | None = None
    future_task_context: str | None = None
    skill_activation: str | None = None


def build_runtime_prompt_packet(
    inputs: AIRuntimeComposeInput,
    *,
    mode: ReplyPromptMode,
    include_tool_policy: bool = True,
) -> PromptPacket:
    """Build a reply prompt packet from runtime materials."""

    recipe_input = ReplyPromptInput(
        persona=inputs.persona,
        scene_type=inputs.scene_type,
        person_profile=inputs.person_profile,
        relationship=inputs.relationship,
        tool_policy=inputs.tool_policy if include_tool_policy else None,
        tool_results=inputs.tool_results,
        memories=inputs.memories,
        conversation_summary=inputs.conversation_summary,
        social_policy_summary=inputs.social_policy_summary,
        capability_awareness=inputs.capability_awareness,
        future_task_context=inputs.future_task_context,
        skill_activation=inputs.skill_activation,
        turns=inputs.turns,
    )
    if mode == "planner":
        return build_reply_planner_packet(recipe_input)
    return build_reply_final_packet(recipe_input)


def build_runtime_prompt_messages(
    inputs: AIRuntimeComposeInput,
    *,
    mode: ReplyPromptMode,
    include_tool_policy: bool = True,
) -> tuple["AIModelMessage", ...]:
    """Build model messages for one reply-generation prompt."""

    return render_messages(
        build_runtime_prompt_packet(
            inputs,
            mode=mode,
            include_tool_policy=include_tool_policy,
        )
    )


def build_pre_tool_reply_packet(
    inputs: AIRuntimeComposeInput,
    *,
    has_tools: bool,
) -> PromptPacket:
    """Build the initial reply packet for either planning or direct reply."""

    if has_tools:
        return build_runtime_prompt_packet(
            inputs,
            mode="planner",
            include_tool_policy=True,
        )
    return build_runtime_prompt_packet(
        inputs,
        mode="roleplay",
        include_tool_policy=False,
    )


def build_roleplay_reply_packet(inputs: AIRuntimeComposeInput) -> PromptPacket:
    """Build the final visible reply packet."""

    return build_runtime_prompt_packet(
        inputs,
        mode="roleplay",
        include_tool_policy=False,
    )


def build_pre_tool_reply_messages(
    inputs: AIRuntimeComposeInput,
    *,
    has_tools: bool,
) -> tuple["AIModelMessage", ...]:
    """Build initial reply messages for direct or tool-planning generation."""

    return render_messages(build_pre_tool_reply_packet(inputs, has_tools=has_tools))


def build_roleplay_reply_messages(
    inputs: AIRuntimeComposeInput,
) -> tuple["AIModelMessage", ...]:
    """Build final visible reply messages."""

    return render_messages(build_roleplay_reply_packet(inputs))
