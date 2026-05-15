"""Prompt-planning boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    from collections.abc import Sequence

    from apeiria.ai.knowledge.models import KnowledgeRetrievalItem
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelMessage
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.context.projection import RuntimeContextPromptView
    from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopResult
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
    memories: "Sequence[AIMemoryDefinition]"
    turns: "Sequence[ChatContextMessageView]"
    profile_card: tuple[str, ...]
    conversation_summary: str | None = None
    social_policy_summary: str | None = None
    capability_awareness: str | None = None
    tool_guidance: str | None = None
    future_task_context: str | None = None
    skill_activation: str | None = None
    rag_chunks: "Sequence[KnowledgeRetrievalItem]" = ()


@dataclass(frozen=True)
class RuntimePromptPlanningInput:
    """Prompt-facing runtime planning materials for reply prompt projection."""

    tool_runtime: "RuntimeToolLoopResult"
    skill_activation: str | None
    has_tools: bool | None = None


def compose_input_from_context_projection(
    view: "RuntimeContextPromptView",
) -> RuntimePromptComposeInput:
    """Translate a context prompt view into recipe compose input."""

    return RuntimePromptComposeInput(
        persona=view.persona,
        scene_type=view.scene_type,
        relationship=view.relationship,
        tool_policy=view.tool_policy,
        tool_results=view.tool_results,
        memories=view.memories,
        turns=view.turns,
        profile_card=view.profile_card,
        conversation_summary=view.conversation_summary,
        social_policy_summary=view.social_policy_summary,
        capability_awareness=view.capability_awareness,
        future_task_context=view.future_task_context,
        skill_activation=view.skill_activation,
        rag_chunks=view.rag_chunks,
    )


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
        profile_card=inputs.profile_card,
        relationship=inputs.relationship,
        tool_policy=inputs.tool_policy if include_tool_policy else None,
        tool_results=inputs.tool_results,
        memories=inputs.memories,
        conversation_summary=inputs.conversation_summary,
        social_policy_summary=inputs.social_policy_summary,
        capability_awareness=inputs.capability_awareness,
        tool_guidance=inputs.tool_guidance,
        future_task_context=inputs.future_task_context,
        skill_activation=inputs.skill_activation,
        rag_chunks=inputs.rag_chunks,
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

    from apeiria.app.ai.runtime.context.projection import project_runtime_context

    projection = project_runtime_context(
        turn=turn,
        context=context,
        social_decision=social_decision,
        tool_runtime=prompt_input.tool_runtime,
        skill_activation=prompt_input.skill_activation,
    )
    compose_input = compose_input_from_context_projection(projection.prompt)
    tool_exposure_plan = getattr(prompt_input, "tool_exposure_plan", None)
    if tool_exposure_plan is None:
        return compose_input

    from apeiria.app.ai.runtime.planning.tool_exposure import build_tool_guidance_text

    return replace(
        compose_input,
        tool_guidance=build_tool_guidance_text(tool_exposure_plan),
    )


def _initial_reply_has_tools(prompt_input: object) -> bool:
    has_tools = getattr(prompt_input, "has_tools", None)
    if has_tools is not None:
        return bool(has_tools)
    has_executable_tools = getattr(prompt_input, "has_executable_tools", False)
    return bool(has_executable_tools)


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
    "compose_input_from_context_projection",
]
