"""Prompt-planning boundary."""

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
from apeiria.app.ai.runtime.planning.social import summarize_social_decision

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import ToolGatewayResult
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.app.ai.runtime.stages import RuntimeTurnPlan
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class RuntimePromptComposeInput:
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


@dataclass(frozen=True)
class RuntimePromptPlanningInput:
    """Prompt-facing runtime planning materials for reply prompt projection."""

    skill_runtime: "ToolGatewayResult"
    skill_activation: str | None
    has_tools: bool | None = None


def build_runtime_prompt_packet(
    inputs: RuntimePromptComposeInput,
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
    inputs: RuntimePromptComposeInput,
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
    inputs: RuntimePromptComposeInput,
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


def build_roleplay_reply_packet(inputs: RuntimePromptComposeInput) -> PromptPacket:
    """Build the final visible reply packet."""

    return build_runtime_prompt_packet(
        inputs,
        mode="roleplay",
        include_tool_policy=False,
    )


def build_pre_tool_reply_messages(
    inputs: RuntimePromptComposeInput,
    *,
    has_tools: bool,
) -> tuple["AIModelMessage", ...]:
    """Build initial reply messages for direct or tool-planning generation."""

    return render_messages(build_pre_tool_reply_packet(inputs, has_tools=has_tools))


def build_roleplay_reply_messages(
    inputs: RuntimePromptComposeInput,
) -> tuple["AIModelMessage", ...]:
    """Build final visible reply messages."""

    return render_messages(build_roleplay_reply_packet(inputs))


def build_initial_reply_prompt_messages(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: "RuntimePromptPlanningInput | RuntimeTurnPlan",
) -> tuple["AIModelMessage", ...]:
    """Build the first model prompt messages used by direct/tool planning."""

    return render_messages(
        build_initial_reply_prompt_packet(
            turn=turn,
            context=context,
            social_decision=social_decision,
            prompt_input=prompt_input,
        )
    )


def build_initial_reply_prompt_packet(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: "RuntimePromptPlanningInput | RuntimeTurnPlan",
) -> PromptPacket:
    """Build the first model prompt packet used by runtime and preview planning."""

    return build_pre_tool_reply_packet(
        build_initial_prompt_compose_input(
            turn=turn,
            context=context,
            social_decision=social_decision,
            prompt_input=prompt_input,
        ),
        has_tools=_initial_reply_has_tools(prompt_input),
    )


def build_initial_prompt_compose_input(
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision",
    prompt_input: "RuntimePromptPlanningInput | RuntimeTurnPlan",
) -> RuntimePromptComposeInput:
    """Build the prompt compose input for the initial reply prompt."""

    return RuntimePromptComposeInput(
        persona=context.persona,
        scene_type=turn.identity.scene_type,
        person_profile=context.person_profile,
        relationship=context.relationship_context,
        tool_policy=prompt_input.skill_runtime.policy_text,
        tool_results=prompt_input.skill_runtime.result_lines,
        memories=context.recalled_memories,
        conversation_summary=context.conversation_summary,
        social_policy_summary=summarize_social_decision(social_decision),
        future_task_context=_build_future_task_context(turn.future_task),
        skill_activation=prompt_input.skill_activation,
        turns=context.turns,
    )


def _initial_reply_has_tools(prompt_input: object) -> bool:
    has_tools = getattr(prompt_input, "has_tools", None)
    if has_tools is not None:
        return bool(has_tools)
    has_executable_tools = getattr(prompt_input, "has_executable_tools", False)
    return bool(has_executable_tools)


def _build_future_task_context(
    task: "AIFutureTaskDefinition | None",
) -> str | None:
    if task is None:
        return None
    return "\n".join(
        (
            f"task_id={task.task_id}",
            f"title={task.title}",
            f"description={task.description}",
            f"trigger_at={task.trigger_at.isoformat()}",
            f"status={task.status}",
        )
    )


__all__ = [
    "RuntimePromptComposeInput",
    "RuntimePromptPlanningInput",
    "build_initial_prompt_compose_input",
    "build_initial_reply_prompt_messages",
    "build_initial_reply_prompt_packet",
    "build_pre_tool_reply_messages",
    "build_pre_tool_reply_packet",
    "build_roleplay_reply_messages",
    "build_roleplay_reply_packet",
    "build_runtime_prompt_messages",
    "build_runtime_prompt_packet",
]
