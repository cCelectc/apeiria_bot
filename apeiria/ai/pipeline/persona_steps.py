"""Runtime persona/model binding steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.access.groups import group_service
from apeiria.ai.model import AIModelBindingTarget
from apeiria.ai.persona.models import AIPersonaBindingTarget
from apeiria.ai.persona.service import (
    ai_persona_service,
    build_persona_render_context,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.conversation.models import (
        ChatContextMessageView,
        ChatSessionIdentity,
    )
    from apeiria.ai.persona.service import AIPersonaRenderContext
    from apeiria.ai.pipeline.prompting import AIPersonaPromptBundleLike
    from apeiria.ai.pipeline.service import AIRuntimeReplyRequest


def build_persona_binding_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIPersonaBindingTarget:
    """Resolve the persona binding target for the current conversation."""

    return AIPersonaBindingTarget(
        conversation_id=identity.session_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
        user_id=identity.subject_id or user_id,
    )


def build_model_binding_target(
    identity: "ChatSessionIdentity",
    user_id: str,
) -> AIModelBindingTarget:
    """Resolve the model binding target for the current conversation."""

    return AIModelBindingTarget(
        conversation_id=identity.session_id,
        group_id=identity.scene_id if identity.scene_type == "group" else None,
        user_id=identity.subject_id or user_id,
    )


def find_recent_user_name(
    turns: list["ChatContextMessageView"],
    user_id: str,
) -> str | None:
    """Find the most recent non-empty author name for the given user id."""

    for turn in reversed(turns):
        if turn.author_role != "user" or turn.author_id != user_id:
            continue
        author_name = (turn.author_name or "").strip()
        if author_name:
            return author_name
    return None


async def load_group_name(identity: "ChatSessionIdentity") -> str | None:
    """Load the group display name for the current identity, if any."""

    if identity.scene_type != "group":
        return None
    group = await group_service.get_group(identity.scene_id)
    return group.group_name if group is not None else None


async def build_persona_render_context_for_reply(
    request: "AIRuntimeReplyRequest",
    *,
    current_time: "datetime",
    turns: list["ChatContextMessageView"],
) -> "AIPersonaRenderContext":
    """Build persona render context from request + recent turns."""

    identity = request.identity
    group_name = await load_group_name(identity)
    return build_persona_render_context(
        bot_id=identity.bot_id,
        current_time=current_time,
        platform=identity.platform,
        scene_type=identity.scene_type,
        scene_id=identity.scene_id,
        session_id=identity.session_id,
        group_name=group_name,
        user_id=request.user_id,
        user_name=find_recent_user_name(turns, request.user_id) or request.user_id,
    )


async def load_persona_bundle(
    *,
    request: "AIRuntimeReplyRequest",
    current_time: "datetime",
    turns: list["ChatContextMessageView"],
) -> "AIPersonaPromptBundleLike | None":
    """Resolve persona binding target and build the prompt bundle."""

    target = build_persona_binding_target(request.identity, request.user_id)
    render_context = await build_persona_render_context_for_reply(
        request,
        current_time=current_time,
        turns=turns,
    )
    return await ai_persona_service.build_persona_prompt_bundle(
        target=target,
        render_context=render_context,
    )
