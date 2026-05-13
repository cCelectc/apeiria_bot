"""Runtime reply input gathering steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.knowledge.models import (
    KnowledgeRetrievalDiagnostics,
    KnowledgeRetrievalResult,
)
from apeiria.ai.knowledge.service import knowledge_retrieval_service
from apeiria.ai.knowledge.settings import knowledge_settings_store
from apeiria.ai.tools import ai_tool_service
from apeiria.app.ai.runtime.context.context_window import build_and_store_context_window
from apeiria.app.ai.runtime.context.memories import retrieve_memories_for_context
from apeiria.app.ai.runtime.context.person_profiles import (
    load_person_profile_for_prompt,
)
from apeiria.app.ai.runtime.context.personas import (
    build_model_binding_target,
    load_persona_bundle,
)
from apeiria.app.ai.runtime.context.relationships import (
    build_relationship_target,
    load_relationship_context,
)
from apeiria.app.ai.runtime.planning.tool_policy import resolve_tool_policy
from apeiria.app.ai.runtime.planning.wake import resolve_initiative_bias

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolDefinition, AIToolPolicy
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class RuntimeConversationContext:
    """Conversation-window materials for one reply turn."""

    turns: list["ChatContextMessageView"]
    conversation_summary: str | None


@dataclass(frozen=True)
class RuntimePersonaContext:
    """Persona and model-binding materials for one reply turn."""

    relationship_target: "AIRelationshipTarget"
    model_target: "AIModelBindingTarget"
    persona: "ReplyPersonaPromptBundleLike | None"


@dataclass(frozen=True)
class RuntimeToolContext:
    """Tool policy and allowed tool materials for one reply turn."""

    tool_policy: "AIToolPolicy"
    allowed_tools: tuple["AIToolDefinition", ...]


@dataclass(frozen=True)
class RuntimeMemoryContext:
    """Memory and relationship materials for one reply turn."""

    recalled_memories: list["AIMemoryDefinition"]
    relationship_context: str | None
    person_profile: tuple[str, ...]
    initiative_bias: float


async def collect_reply_inputs(
    turn: "RuntimeTurnInput",
    current_time: "datetime",
) -> "RuntimeContextMaterials":
    """Collect all prompt-facing materials needed to decide and generate a reply."""

    from apeiria.app.ai.runtime.session.context import RuntimeContextMaterials

    conversation = await collect_conversation_context(turn)
    persona_context = await collect_persona_context(
        turn=turn,
        current_time=current_time,
        turns=conversation.turns,
    )
    tool_context = await collect_tool_context(turn)
    memory_context = await collect_memory_context(
        turn=turn,
        relationship_target=persona_context.relationship_target,
    )
    rag_result = await retrieve_rag_for_context(
        query_text=turn.message_text,
        limit=3,
    )
    return RuntimeContextMaterials(
        turns=conversation.turns,
        conversation_summary=conversation.conversation_summary,
        relationship_target=persona_context.relationship_target,
        model_target=persona_context.model_target,
        tool_policy=tool_context.tool_policy,
        persona=persona_context.persona,
        recalled_memories=memory_context.recalled_memories,
        relationship_context=memory_context.relationship_context,
        person_profile=memory_context.person_profile,
        allowed_tools=tool_context.allowed_tools,
        initiative_bias=memory_context.initiative_bias,
        rag_chunks=rag_result.items,
        rag_diagnostics=rag_result.diagnostics,
    )


async def gather_reply_inputs(
    turn: "RuntimeTurnInput",
    current_time: "datetime",
) -> "RuntimeContextMaterials":
    """Collect runtime-owned prompt-facing materials for context assembly."""

    return await collect_reply_inputs(turn, current_time)


async def collect_conversation_context(
    turn: "RuntimeTurnInput",
) -> RuntimeConversationContext:
    """Collect conversation-window context for one reply turn."""

    turns, conversation_summary = await build_and_store_context_window(
        identity=turn.identity,
    )
    return RuntimeConversationContext(
        turns=turns,
        conversation_summary=conversation_summary,
    )


async def collect_persona_context(
    *,
    turn: "RuntimeTurnInput",
    current_time: "datetime",
    turns: list["ChatContextMessageView"],
) -> RuntimePersonaContext:
    """Collect persona and model-binding context for one reply turn."""

    relationship_target = build_relationship_target(turn.identity, turn.user_id)
    return RuntimePersonaContext(
        relationship_target=relationship_target,
        model_target=build_model_binding_target(turn.identity, turn.user_id),
        persona=await load_persona_bundle(
            turn=turn,
            current_time=current_time,
            turns=turns,
        ),
    )


async def collect_tool_context(
    turn: "RuntimeTurnInput",
) -> RuntimeToolContext:
    """Collect tool policy and allowed capabilities for one reply turn."""

    tool_policy = await resolve_tool_policy(
        turn.identity,
        is_tome=turn.is_tome,
    )
    return RuntimeToolContext(
        tool_policy=tool_policy,
        allowed_tools=tuple(ai_tool_service.list_allowed_tools(tool_policy)),
    )


async def collect_memory_context(
    *,
    turn: "RuntimeTurnInput",
    relationship_target: "AIRelationshipTarget",
) -> RuntimeMemoryContext:
    """Collect memory, relationship, profile, and initiative context."""

    return RuntimeMemoryContext(
        recalled_memories=await retrieve_memories_for_context(
            identity=turn.identity,
            user_id=turn.user_id,
            query_text=turn.message_text,
        ),
        relationship_context=await load_relationship_context(
            target=relationship_target,
        ),
        person_profile=await load_person_profile_for_prompt(
            identity=turn.identity,
            user_id=turn.user_id,
        ),
        initiative_bias=await resolve_initiative_bias(
            relationship_target=relationship_target,
        ),
    )


async def retrieve_rag_for_context(
    *,
    query_text: str,
    limit: int,
) -> KnowledgeRetrievalResult:
    """Retrieve runtime RAG context only when explicitly enabled."""

    if not knowledge_settings_store.get().rag_enabled:
        return KnowledgeRetrievalResult(
            items=(),
            diagnostics=KnowledgeRetrievalDiagnostics(degradation_reason="disabled"),
        )
    return await knowledge_retrieval_service.retrieve(
        query_text=query_text,
        limit=limit,
        mutate_embeddings=False,
    )
