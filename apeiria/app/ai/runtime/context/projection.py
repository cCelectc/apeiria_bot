"""Read-model projection for gathered runtime context materials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, TypeGuard

from apeiria.app.ai.runtime.planning.social import summarize_social_decision

if TYPE_CHECKING:
    from apeiria.ai.knowledge.models import (
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
    )
    from apeiria.ai.memory import AIMemoryDefinition, AIMemoryRetrievalDiagnostics
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.conversation.models import ChatContextMessageView

RuntimeContextProjectionMode = Literal["runtime", "preview"]


class RuntimeContextToolRuntimeView(Protocol):
    """Minimal tool-loop prompt result shape consumed by context projection."""

    @property
    def policy_text(self) -> str: ...

    @property
    def result_lines(self) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class RuntimeContextPromptView:
    """Prompt-facing view derived from gathered runtime context."""

    persona: "ReplyPersonaPromptBundleLike | None"
    scene_type: str
    relationship: str | None
    tool_policy: str | None
    tool_results: tuple[str, ...]
    memories: tuple["AIMemoryDefinition", ...]
    turns: tuple["ChatContextMessageView", ...]
    person_profile: tuple[str, ...]
    conversation_summary: str | None
    social_policy_summary: str | None
    capability_awareness: str | None = None
    future_task_context: str | None = None
    skill_activation: str | None = None
    rag_chunks: tuple["KnowledgeRetrievalItem", ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeContextPreviewView:
    """Preview-facing context fields derived from the shared projection."""

    persona: "ReplyPersonaPromptBundleLike | None"
    conversation_summary: str | None
    relationship_context: str | None
    tool_policy_text: str
    tool_results: tuple[str, ...]
    memories: tuple["AIMemoryDefinition", ...]
    turns: tuple["ChatContextMessageView", ...]
    person_profile: tuple[str, ...]
    capability_awareness: str | None = None
    rag_chunks: tuple["KnowledgeRetrievalItem", ...] = ()
    rag_diagnostics: "KnowledgeRetrievalDiagnostics | None" = None


@dataclass(frozen=True, slots=True)
class RuntimeContextDiagnostics:
    """Bounded context-shape metadata for runtime and preview reads."""

    projection_mode: RuntimeContextProjectionMode
    turn_count: int
    recalled_memory_count: int
    memory_layers: tuple[str, ...]
    memory_layer_counts: dict[str, int]
    memory_use_mode_counts: dict[str, int]
    memory_lifecycle_counts: dict[str, int]
    has_persona: bool
    has_relationship_context: bool
    person_profile_line_count: int
    has_conversation_summary: bool
    allowed_capability_count: int
    has_capability_awareness: bool
    has_future_task_context: bool
    rag_enabled: bool
    rag_selected_count: int
    rag_candidate_count: int
    rag_missing_embedding_count: int
    rag_stale_embedding_count: int
    rag_rerank_status: str | None
    memory_selected: tuple[dict[str, object], ...] = ()
    memory_excluded: tuple[dict[str, object], ...] = ()
    rag_degradation_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the diagnostics as a compact serializable mapping."""

        return {
            "projection_mode": self.projection_mode,
            "turn_count": self.turn_count,
            "recalled_memory_count": self.recalled_memory_count,
            "memory_layers": self.memory_layers,
            "memory_layer_counts": self.memory_layer_counts,
            "memory_use_mode_counts": self.memory_use_mode_counts,
            "memory_lifecycle_counts": self.memory_lifecycle_counts,
            "memory_selected": list(self.memory_selected),
            "memory_excluded": list(self.memory_excluded),
            "has_persona": self.has_persona,
            "has_relationship_context": self.has_relationship_context,
            "person_profile_line_count": self.person_profile_line_count,
            "has_conversation_summary": self.has_conversation_summary,
            "allowed_capability_count": self.allowed_capability_count,
            "has_capability_awareness": self.has_capability_awareness,
            "has_future_task_context": self.has_future_task_context,
            "rag_enabled": self.rag_enabled,
            "rag_selected_count": self.rag_selected_count,
            "rag_candidate_count": self.rag_candidate_count,
            "rag_missing_embedding_count": self.rag_missing_embedding_count,
            "rag_stale_embedding_count": self.rag_stale_embedding_count,
            "rag_rerank_status": self.rag_rerank_status,
            "rag_degradation_reason": self.rag_degradation_reason,
        }


@dataclass(frozen=True, slots=True)
class RuntimeContextProjection:
    """Shared read-model projection for one runtime context snapshot."""

    prompt: RuntimeContextPromptView
    preview: RuntimeContextPreviewView
    diagnostics: RuntimeContextDiagnostics


def project_runtime_context(  # noqa: PLR0913
    *,
    turn: "RuntimeTurnInput",
    context: "RuntimeContextMaterials",
    social_decision: "ReplyStrategyDecision | None",
    tool_runtime: RuntimeContextToolRuntimeView,
    skill_activation: str | None = None,
    capability_awareness: str | None = None,
    projection_mode: RuntimeContextProjectionMode = "runtime",
) -> RuntimeContextProjection:
    """Project gathered context materials into prompt, preview, and diagnostics."""

    future_task_context = _build_future_task_context(turn.future_task)
    prompt = RuntimeContextPromptView(
        persona=context.persona,
        scene_type=turn.identity.scene_type,
        relationship=context.relationship_context,
        tool_policy=tool_runtime.policy_text,
        tool_results=tool_runtime.result_lines,
        memories=tuple(context.recalled_memories),
        turns=tuple(context.turns),
        person_profile=context.person_profile,
        conversation_summary=context.conversation_summary,
        social_policy_summary=(
            summarize_social_decision(social_decision)
            if social_decision is not None
            else None
        ),
        capability_awareness=capability_awareness,
        future_task_context=future_task_context,
        skill_activation=skill_activation,
        rag_chunks=getattr(context, "rag_chunks", ()),
    )
    preview = RuntimeContextPreviewView(
        persona=context.persona,
        conversation_summary=context.conversation_summary,
        relationship_context=context.relationship_context,
        tool_policy_text=tool_runtime.policy_text,
        tool_results=tool_runtime.result_lines,
        memories=tuple(context.recalled_memories),
        turns=tuple(context.turns),
        person_profile=context.person_profile,
        capability_awareness=capability_awareness,
        rag_chunks=getattr(context, "rag_chunks", ()),
        rag_diagnostics=getattr(context, "rag_diagnostics", None),
    )
    return RuntimeContextProjection(
        prompt=prompt,
        preview=preview,
        diagnostics=RuntimeContextDiagnostics(
            projection_mode=projection_mode,
            turn_count=len(context.turns),
            recalled_memory_count=len(context.recalled_memories),
            memory_layers=_memory_layers(context.recalled_memories),
            memory_layer_counts=_memory_layer_counts(context.recalled_memories),
            memory_use_mode_counts=_memory_diagnostics_counts(
                context.memory_diagnostics,
                "use_mode_counts",
            ),
            memory_lifecycle_counts=_memory_diagnostics_counts(
                context.memory_diagnostics,
                "lifecycle_counts",
            ),
            memory_selected=_memory_diagnostics_items(
                context.memory_diagnostics,
                "selected",
            ),
            memory_excluded=_memory_diagnostics_items(
                context.memory_diagnostics,
                "excluded",
            ),
            has_persona=context.persona is not None,
            has_relationship_context=bool(context.relationship_context),
            person_profile_line_count=len(context.person_profile),
            has_conversation_summary=bool(context.conversation_summary),
            allowed_capability_count=len(context.allowed_tools),
            has_capability_awareness=capability_awareness is not None,
            has_future_task_context=future_task_context is not None,
            rag_enabled=_rag_enabled(getattr(context, "rag_diagnostics", None)),
            rag_selected_count=len(getattr(context, "rag_chunks", ())),
            rag_candidate_count=_rag_candidate_count(
                getattr(context, "rag_diagnostics", None)
            ),
            rag_missing_embedding_count=_rag_missing_embedding_count(
                getattr(context, "rag_diagnostics", None)
            ),
            rag_stale_embedding_count=_rag_stale_embedding_count(
                getattr(context, "rag_diagnostics", None)
            ),
            rag_rerank_status=_rag_rerank_status(
                getattr(context, "rag_diagnostics", None)
            ),
            rag_degradation_reason=_rag_degradation_reason(
                getattr(context, "rag_diagnostics", None)
            ),
        ),
    )


def _memory_layers(memories: list["AIMemoryDefinition"]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(memory.memory_layer for memory in memories))


def _memory_layer_counts(memories: list["AIMemoryDefinition"]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for memory in memories:
        counts[memory.memory_layer] = counts.get(memory.memory_layer, 0) + 1
    return counts


def _memory_diagnostics_counts(
    diagnostics: object,
    key: str,
) -> dict[str, int]:
    if not _is_memory_diagnostics(diagnostics):
        return {}
    data = diagnostics.as_dict()
    value = data.get(key)
    if not isinstance(value, dict):
        return {}
    return {
        str(item_key): int(item_value)
        for item_key, item_value in value.items()
        if isinstance(item_value, int)
    }


def _memory_diagnostics_items(
    diagnostics: object,
    key: str,
) -> tuple[dict[str, object], ...]:
    if not _is_memory_diagnostics(diagnostics):
        return ()
    data = diagnostics.as_dict()
    value = data.get(key)
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item for item in value if isinstance(item, dict))[:8]


def _is_memory_diagnostics(
    value: object,
) -> "TypeGuard[AIMemoryRetrievalDiagnostics]":
    from apeiria.ai.memory import AIMemoryRetrievalDiagnostics

    return isinstance(value, AIMemoryRetrievalDiagnostics)


def _rag_enabled(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> bool:
    if diagnostics is None:
        return False
    return diagnostics.degradation_reason != "disabled"


def _rag_candidate_count(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> int:
    return diagnostics.candidate_count if diagnostics is not None else 0


def _rag_missing_embedding_count(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> int:
    return diagnostics.missing_embedding_count if diagnostics is not None else 0


def _rag_stale_embedding_count(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> int:
    return diagnostics.stale_embedding_count if diagnostics is not None else 0


def _rag_rerank_status(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> str | None:
    return diagnostics.rerank_status if diagnostics is not None else None


def _rag_degradation_reason(
    diagnostics: "KnowledgeRetrievalDiagnostics | None",
) -> str | None:
    return diagnostics.degradation_reason if diagnostics is not None else None


def _build_future_task_context(
    turn_future_task: "AIFutureTaskDefinition | None",
) -> str | None:
    if turn_future_task is None:
        return None
    return "\n".join(
        (
            f"task_id={turn_future_task.task_id}",
            f"title={turn_future_task.title}",
            f"description={turn_future_task.description}",
            f"trigger_at={turn_future_task.trigger_at.isoformat()}",
            f"status={turn_future_task.status}",
        )
    )


__all__ = [
    "RuntimeContextDiagnostics",
    "RuntimeContextPreviewView",
    "RuntimeContextProjection",
    "RuntimeContextPromptView",
    "RuntimeContextToolRuntimeView",
    "project_runtime_context",
]
