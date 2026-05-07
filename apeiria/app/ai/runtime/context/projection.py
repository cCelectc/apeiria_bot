"""Read-model projection for gathered runtime context materials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from apeiria.app.ai.runtime.planning.social import summarize_social_decision

if TYPE_CHECKING:
    from apeiria.ai.memory import AIMemoryDefinition
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.session.context import (
        RuntimeContextMaterials,
        RuntimeTurnInput,
    )
    from apeiria.conversation.models import ChatContextMessageView

RuntimeContextProjectionMode = Literal["runtime", "preview"]


class RuntimeContextSkillRuntimeView(Protocol):
    """Minimal skill/tool prompt result shape consumed by context projection."""

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


@dataclass(frozen=True, slots=True)
class RuntimeContextDiagnostics:
    """Bounded context-shape metadata for runtime and preview reads."""

    projection_mode: RuntimeContextProjectionMode
    turn_count: int
    recalled_memory_count: int
    memory_layers: tuple[str, ...]
    has_persona: bool
    has_relationship_context: bool
    person_profile_line_count: int
    has_conversation_summary: bool
    allowed_capability_count: int
    has_capability_awareness: bool
    has_future_task_context: bool

    def as_dict(self) -> dict[str, object]:
        """Return the diagnostics as a compact serializable mapping."""

        return {
            "projection_mode": self.projection_mode,
            "turn_count": self.turn_count,
            "recalled_memory_count": self.recalled_memory_count,
            "memory_layers": self.memory_layers,
            "has_persona": self.has_persona,
            "has_relationship_context": self.has_relationship_context,
            "person_profile_line_count": self.person_profile_line_count,
            "has_conversation_summary": self.has_conversation_summary,
            "allowed_capability_count": self.allowed_capability_count,
            "has_capability_awareness": self.has_capability_awareness,
            "has_future_task_context": self.has_future_task_context,
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
    skill_runtime: RuntimeContextSkillRuntimeView,
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
        tool_policy=skill_runtime.policy_text,
        tool_results=skill_runtime.result_lines,
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
    )
    preview = RuntimeContextPreviewView(
        persona=context.persona,
        conversation_summary=context.conversation_summary,
        relationship_context=context.relationship_context,
        tool_policy_text=skill_runtime.policy_text,
        tool_results=skill_runtime.result_lines,
        memories=tuple(context.recalled_memories),
        turns=tuple(context.turns),
        person_profile=context.person_profile,
        capability_awareness=capability_awareness,
    )
    return RuntimeContextProjection(
        prompt=prompt,
        preview=preview,
        diagnostics=RuntimeContextDiagnostics(
            projection_mode=projection_mode,
            turn_count=len(context.turns),
            recalled_memory_count=len(context.recalled_memories),
            memory_layers=_memory_layers(context.recalled_memories),
            has_persona=context.persona is not None,
            has_relationship_context=bool(context.relationship_context),
            person_profile_line_count=len(context.person_profile),
            has_conversation_summary=bool(context.conversation_summary),
            allowed_capability_count=len(context.allowed_tools),
            has_capability_awareness=capability_awareness is not None,
            has_future_task_context=future_task_context is not None,
        ),
    )


def _memory_layers(memories: list["AIMemoryDefinition"]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(memory.memory_layer for memory in memories))


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
    "RuntimeContextSkillRuntimeView",
    "project_runtime_context",
]
