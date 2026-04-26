"""Runtime prompt composition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.pipeline.prompting import (
    AIPromptMode,
    AIReplyPromptChannels,
    AIReplyPromptContext,
    build_reply_prompt_channels,
    render_reply_prompt,
)

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.app.ai.pipeline.prompting import AIPersonaPromptBundleLike
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class AIRuntimeComposeInput:
    """Structured runtime inputs for reply prompt composition."""

    persona: "AIPersonaPromptBundleLike | None"
    scene_type: str
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: list["AIMemoryDefinition"]
    turns: list["ChatContextMessageView"]
    person_profile: tuple[str, ...]
    conversation_summary: str | None = None
    social_policy_summary: str | None = None
    future_task_context: str | None = None
    skill_activation: str | None = None


def compose_reply_prompt(
    inputs: AIRuntimeComposeInput,
    *,
    mode: AIPromptMode,
    include_tool_policy: bool = True,
) -> str:
    """Compose one runtime prompt from separated runtime channels."""

    return render_reply_prompt(
        build_runtime_prompt_channels(
            inputs,
            mode=mode,
            include_tool_policy=include_tool_policy,
        )
    )


def build_runtime_prompt_channels(
    inputs: AIRuntimeComposeInput,
    *,
    mode: AIPromptMode,
    include_tool_policy: bool = True,
) -> AIReplyPromptChannels:
    """Build structured runtime prompt channels without rendering."""

    return build_reply_prompt_channels(
        AIReplyPromptContext(
            persona=inputs.persona,
            scene_type=inputs.scene_type,
            person_profile=inputs.person_profile,
            relationship=inputs.relationship,
            tool_policy=inputs.tool_policy if include_tool_policy else None,
            tool_results=inputs.tool_results,
            memories=inputs.memories,
            conversation_summary=inputs.conversation_summary,
            social_policy=inputs.social_policy_summary,
            future_task=inputs.future_task_context,
            skill_activation=inputs.skill_activation,
            turns=inputs.turns,
        ),
        mode=mode,
    )


def compose_pre_tool_reply_prompt(
    inputs: AIRuntimeComposeInput,
    *,
    has_tools: bool,
) -> str:
    """Compose the first runtime prompt.

    When tools are available this stays in the planning/orchestration lane.
    When no tools are available, skip the extra tool-policy layer and use the
    cleaner roleplay prompt directly.
    """

    if has_tools:
        return compose_reply_prompt(
            inputs,
            mode="planner",
            include_tool_policy=True,
        )
    return compose_reply_prompt(
        inputs,
        mode="roleplay",
        include_tool_policy=False,
    )


def compose_roleplay_reply_prompt(inputs: AIRuntimeComposeInput) -> str:
    """Compose the final roleplay reply prompt after tool execution.

    This stage intentionally omits tool-policy instructions so the final model
    sees persona, relationship, memories, conversation, and distilled tool
    results without the full structural policy layer.
    """

    return compose_reply_prompt(
        inputs,
        mode="roleplay",
        include_tool_policy=False,
    )
