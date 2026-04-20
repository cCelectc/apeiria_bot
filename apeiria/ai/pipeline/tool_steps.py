"""Runtime tool policy / observation steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.conversation.service import ChatMessageCreate, chat_session_service
from apeiria.ai.tools.policy import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.ai.conversation.models import ChatSessionIdentity
    from apeiria.ai.tools.models import AIToolPolicy, AIToolTurnCreateInput


async def resolve_tool_policy(
    session: "AsyncSession",
    identity: "ChatSessionIdentity",
    *,
    is_tome: bool,
) -> "AIToolPolicy":
    """Resolve the scene-scoped tool policy for the current conversation."""

    return await ai_tool_policy_binding_service.resolve_scene_policy(
        session,
        scene_context=AIToolSceneContext(
            scope_type=identity.scene_type,
            is_tome=is_tome,
        ),
        target=AIToolPolicyBindingTarget(
            conversation_id=identity.session_id,
            group_id=identity.scene_id if identity.scene_type == "group" else None,
            user_id=identity.subject_id,
        ),
    )


async def append_tool_observation_turns(
    session: "AsyncSession",
    *,
    identity: "ChatSessionIdentity",
    trace_id: str,
    tool_turns: tuple["AIToolTurnCreateInput", ...],
) -> None:
    """Persist tool observation turns under the given trace id."""

    for index, turn in enumerate(tool_turns):
        await chat_session_service.append_message(
            session,
            identity,
            ChatMessageCreate(
                author_role="tool",
                author_id=turn.author_id,
                text_content=turn.text_content,
                message_kind="tool",
                meta={
                    "trace_id": trace_id,
                    "index": index,
                    **turn.meta,
                },
            ),
        )
