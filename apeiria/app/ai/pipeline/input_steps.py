"""Runtime reply input gathering steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.tools import ai_tool_service
from apeiria.app.ai.pipeline.context_window_steps import build_and_store_context_window
from apeiria.app.ai.pipeline.memory_steps import retrieve_memories_for_context
from apeiria.app.ai.pipeline.person_profile_steps import load_person_profile_for_prompt
from apeiria.app.ai.pipeline.persona_steps import (
    build_model_binding_target,
    load_persona_bundle,
)
from apeiria.app.ai.pipeline.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.pipeline.reply_strategy_steps import resolve_initiative_bias
from apeiria.app.ai.pipeline.tool_steps import resolve_tool_policy

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolPolicy, AIToolSpec
    from apeiria.app.ai.pipeline.relationship_steps import AIRelationshipTarget
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class ReplyInputs:
    """Aggregated prompt/context materials for one reply turn."""

    turns: list["ChatContextMessageView"]
    conversation_summary: str | None
    relationship_target: "AIRelationshipTarget"
    model_target: "AIModelBindingTarget"
    tool_policy: "AIToolPolicy"
    persona: "ReplyPersonaPromptBundleLike | None"
    recalled_memories: list["AIMemoryDefinition"]
    relationship_context: str | None
    person_profile: tuple[str, ...]
    allowed_tools: tuple["AIToolSpec", ...]
    initiative_bias: float


async def gather_reply_inputs(
    request: "AIRuntimeReplyRequest",
    current_time: "datetime",
) -> ReplyInputs:
    """Collect all prompt-facing materials needed to decide and generate a reply."""

    identity = request.identity

    turns, conversation_summary = await build_and_store_context_window(
        identity=identity,
    )
    relationship_target = build_relationship_target(identity, request.user_id)
    model_target = build_model_binding_target(identity, request.user_id)
    tool_policy = await resolve_tool_policy(
        identity,
        is_tome=request.is_tome,
    )
    persona = await load_persona_bundle(
        request=request,
        current_time=current_time,
        turns=turns,
    )
    recalled_memories = await retrieve_memories_for_context(
        identity=identity,
        user_id=request.user_id,
        query_text=request.message_text,
    )
    relationship_context = await load_relationship_context(
        target=relationship_target,
    )
    person_profile = await load_person_profile_for_prompt(
        identity=identity,
        user_id=request.user_id,
    )
    allowed_tools = tuple(ai_tool_service.list_allowed_tools(tool_policy))
    initiative_bias = await resolve_initiative_bias(
        relationship_target=relationship_target,
    )
    return ReplyInputs(
        turns=turns,
        conversation_summary=conversation_summary,
        relationship_target=relationship_target,
        model_target=model_target,
        tool_policy=tool_policy,
        persona=persona,
        recalled_memories=recalled_memories,
        relationship_context=relationship_context,
        person_profile=person_profile,
        allowed_tools=allowed_tools,
        initiative_bias=initiative_bias,
    )
