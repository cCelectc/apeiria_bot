"""Runtime generation-stage dataclasses and gather step."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.runtime.context_window_steps import build_and_store_context_window
from apeiria.app.ai.runtime.memory_steps import (
    load_person_profile_for_prompt,
    recall_memories,
)
from apeiria.app.ai.runtime.persona_steps import (
    build_model_binding_target,
    load_persona_bundle,
)
from apeiria.app.ai.runtime.relationship_steps import (
    build_relationship_target,
    load_relationship_context,
    update_relationship_state,
)
from apeiria.app.ai.runtime.reply_strategy_steps import resolve_initiative_bias
from apeiria.app.ai.runtime.tool_steps import resolve_tool_policy
from apeiria.app.ai.tools.service import ai_tool_service

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ChatContextMessageView
    from apeiria.app.ai.memory.models import AIMemoryDefinition
    from apeiria.app.ai.model import AIModelBindingTarget
    from apeiria.app.ai.runtime.prompting import AIPersonaPromptBundleLike
    from apeiria.app.ai.runtime.relationship_steps import AIRelationshipTarget
    from apeiria.app.ai.runtime.service import AIRuntimeReplyRequest
    from apeiria.app.ai.tools.models import AIToolPolicy, AIToolSpec


@dataclass(frozen=True)
class ReplyInputs:
    """Aggregated prompt/context materials for one reply turn."""

    turns: list["ChatContextMessageView"]
    conversation_summary: str | None
    relationship_target: "AIRelationshipTarget"
    model_target: "AIModelBindingTarget"
    tool_policy: "AIToolPolicy"
    persona: "AIPersonaPromptBundleLike | None"
    recalled_memories: list["AIMemoryDefinition"]
    relationship_context: str | None
    person_profile: tuple[str, ...]
    allowed_tools: tuple["AIToolSpec", ...]
    initiative_bias: float


async def gather_reply_inputs(
    session: "AsyncSession",
    request: "AIRuntimeReplyRequest",
    current_time: "datetime",
) -> ReplyInputs:
    """Collect all prompt-facing materials needed to decide and generate a reply."""

    identity = request.identity

    turns, conversation_summary = await build_and_store_context_window(
        session,
        identity=identity,
    )
    relationship_target = build_relationship_target(identity, request.user_id)
    model_target = build_model_binding_target(identity, request.user_id)
    tool_policy = await resolve_tool_policy(
        session,
        identity,
        is_tome=request.is_tome,
    )
    persona = await load_persona_bundle(
        session,
        request=request,
        current_time=current_time,
        turns=turns,
    )
    if request.runtime_mode == "message" and request.sentiment is not None:
        await update_relationship_state(
            session,
            target=relationship_target,
            sentiment=request.sentiment,
            is_tome=request.is_tome,
        )
    recalled_memories = await recall_memories(
        session,
        identity=identity,
        user_id=request.user_id,
        query_text=request.message_text,
    )
    relationship_context = await load_relationship_context(
        session,
        target=relationship_target,
    )
    person_profile = await load_person_profile_for_prompt(
        session,
        identity=identity,
        user_id=request.user_id,
    )
    allowed_tools = tuple(ai_tool_service.list_allowed_tools(tool_policy))
    initiative_bias = await resolve_initiative_bias(
        session,
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
