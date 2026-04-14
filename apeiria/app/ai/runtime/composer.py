"""Runtime prompt composition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.prompting import (
    AIReplyPromptContext,
    build_reply_prompt_channels,
    render_reply_prompt,
)

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import AIContextTurnView
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.runtime.prompting import AIPersonaPromptBundleLike


@dataclass(frozen=True)
class AIRuntimeComposeInput:
    """Structured runtime inputs for reply prompt composition."""

    persona: "AIPersonaPromptBundleLike | None"
    relationship: str | None
    skill_policy: str | None
    skill_results: tuple[str, ...]
    memories: list["AIMemoryDefinition"]
    turns: list["AIContextTurnView"]
    conversation_summary: str | None = None
    social_policy_summary: str | None = None
    future_task_context: str | None = None


def compose_reply_prompt(inputs: AIRuntimeComposeInput) -> str:
    """Compose the tool-planning prompt from separated runtime channels."""

    return render_reply_prompt(
        build_reply_prompt_channels(
            AIReplyPromptContext(
                persona=inputs.persona,
                relationship=inputs.relationship,
                tool_policy=inputs.skill_policy,
                tool_results=inputs.skill_results,
                memories=inputs.memories,
                conversation_summary=inputs.conversation_summary,
                social_policy=inputs.social_policy_summary,
                future_task=inputs.future_task_context,
                turns=inputs.turns,
            )
        )
    )


def compose_roleplay_reply_prompt(inputs: AIRuntimeComposeInput) -> str:
    """Compose the final roleplay reply prompt after tool execution.

    This stage intentionally omits tool-policy instructions so the final model
    sees persona, relationship, memories, conversation, and distilled tool
    results without the full structural policy layer.
    """

    return render_reply_prompt(
        build_reply_prompt_channels(
            AIReplyPromptContext(
                persona=inputs.persona,
                relationship=inputs.relationship,
                tool_policy=None,
                tool_results=inputs.skill_results,
                memories=inputs.memories,
                conversation_summary=inputs.conversation_summary,
                social_policy=inputs.social_policy_summary,
                future_task=inputs.future_task_context,
                turns=inputs.turns,
            )
        )
    )
