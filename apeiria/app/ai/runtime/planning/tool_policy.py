"""Runtime tool policy / observation steps extracted from the orchestration layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.tools import (
    AIToolPolicyBindingTarget,
    AIToolSceneContext,
    ai_tool_policy_binding_service,
)
from apeiria.conversation.contracts import ChatMessageCreate
from apeiria.conversation.service import chat_session_service

if TYPE_CHECKING:
    from apeiria.ai.tools import AIToolPolicy, AIToolTurnCreateInput
    from apeiria.conversation.models import ChatSessionIdentity


async def resolve_tool_policy(
    identity: "ChatSessionIdentity",
    *,
    is_tome: bool,
) -> "AIToolPolicy":
    """Resolve the scene-scoped tool policy for the current conversation."""

    return await ai_tool_policy_binding_service.resolve_scene_policy(
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
    *,
    identity: "ChatSessionIdentity",
    trace_id: str,
    tool_turns: tuple["AIToolTurnCreateInput", ...],
) -> None:
    """Persist tool observation turns under the given trace id."""

    for index, turn in enumerate(tool_turns):
        await chat_session_service.append_message(
            identity,
            ChatMessageCreate(
                author_role="tool",
                author_id=turn.author_id,
                text_content=turn.text_content,
                message_kind="tool",
                turn_disposition="tool",
                meta={
                    "trace_id": trace_id,
                    "index": index,
                    **turn.meta,
                },
            ),
        )
