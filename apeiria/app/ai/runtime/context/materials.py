"""Runtime reply input gathering steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.knowledge.models import (
    KnowledgeRetrievalDiagnostics,
    KnowledgeRetrievalItem,
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

    from apeiria.ai.capabilities import AICapabilityContract
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.model import AIModelBindingTarget
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolPolicy
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.conversation.models import ChatContextMessageView


@dataclass(frozen=True)
class RuntimeContextInputBundle:
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
    allowed_tools: tuple["AICapabilityContract", ...]
    initiative_bias: float
    rag_chunks: tuple[KnowledgeRetrievalItem, ...] = ()
    rag_diagnostics: KnowledgeRetrievalDiagnostics | None = None


async def collect_reply_inputs(
    request: "AIRuntimeTurnRequest",
    current_time: "datetime",
) -> RuntimeContextInputBundle:
    """Collect all prompt-facing materials needed to decide and generate a reply."""

    identity = request.identity
    turn = request.to_runtime_turn_input()

    turns, conversation_summary = await build_and_store_context_window(
        identity=identity,
    )
    relationship_target = build_relationship_target(identity, turn.user_id)
    model_target = build_model_binding_target(identity, turn.user_id)
    tool_policy = await resolve_tool_policy(
        identity,
        is_tome=turn.is_tome,
    )
    persona = await load_persona_bundle(
        request=request,
        current_time=current_time,
        turns=turns,
    )
    recalled_memories = await retrieve_memories_for_context(
        identity=identity,
        user_id=turn.user_id,
        query_text=turn.message_text,
    )
    relationship_context = await load_relationship_context(
        target=relationship_target,
    )
    person_profile = await load_person_profile_for_prompt(
        identity=identity,
        user_id=turn.user_id,
    )
    allowed_tools = tuple(ai_tool_service.list_allowed_tools(tool_policy))
    initiative_bias = await resolve_initiative_bias(
        relationship_target=relationship_target,
    )
    rag_result = await retrieve_rag_for_context(
        query_text=turn.message_text,
        limit=3,
    )
    return RuntimeContextInputBundle(
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
        rag_chunks=rag_result.items,
        rag_diagnostics=rag_result.diagnostics,
    )


async def gather_reply_inputs(
    turn: "RuntimeTurnInput",
    current_time: "datetime",
) -> "RuntimeContextMaterials":
    """Collect and adapt prompt-facing materials for runtime context assembly."""

    from apeiria.app.ai.runtime.session.context import RuntimeContextMaterials

    return RuntimeContextMaterials.from_context_input_bundle(
        await collect_reply_inputs(turn.to_turn_request(), current_time)
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
